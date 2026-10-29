"""Repeated stratified cross-validation with pooled out-of-fold predictions (D-B2-5).

Every row gets one prediction per repeat from a model that never saw it; the pooled
prediction is the per-row mean. n stays 1,000: repeats are not extra applicants (C11).
Bootstrap intervals resample rows of the pooled predictions, so they capture sampling
noise; the spread across repeats is reported separately as model-fitting noise.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

from credit.pipeline.attributes import MODEL_FEATURES
from credit.pipeline.model import SEED
from credit.pipeline.policy import COST_APPROVE_BAD, COST_DECLINE_GOOD, THRESHOLD

N_SPLITS, N_REPEATS, N_BOOT = 5, 5, 2000
ECE_BINS = 10


def oof_predictions(frame: pd.DataFrame, make: Callable[[], CalibratedClassifierCV]) -> np.ndarray:
    """Array of shape (n_repeats, n_rows): out-of-fold P(bad)."""
    X, y = frame[list(MODEL_FEATURES)], frame["bad"].to_numpy()
    out = np.full((N_REPEATS, len(frame)), np.nan)
    splitter = RepeatedStratifiedKFold(n_splits=N_SPLITS, n_repeats=N_REPEATS, random_state=SEED)
    for i, (train, test) in enumerate(splitter.split(X, y)):
        model = clone(make()).fit(X.iloc[train], y[train])
        out[i // N_SPLITS, test] = model.predict_proba(X.iloc[test])[:, 1]
    if np.isnan(out).any():
        raise RuntimeError("every row must receive one prediction per repeat")
    return out


def expected_cost(y: np.ndarray, p: np.ndarray, threshold: float = THRESHOLD) -> float:
    decline = p > threshold
    approved_bad = np.sum(~decline & (y == 1))
    declined_good = np.sum(decline & (y == 0))
    return float((COST_APPROVE_BAD * approved_bad + COST_DECLINE_GOOD * declined_good) / len(y))


def ece(y: np.ndarray, p: np.ndarray, bins: int = ECE_BINS) -> float:
    """Expected calibration error, equal-width bins, weighted by bin size."""
    idx = np.minimum((p * bins).astype(int), bins - 1)
    total = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return float(total)


METRICS: dict[str, Callable[[np.ndarray, np.ndarray], float]] = {
    "auroc": lambda y, p: float(roc_auc_score(y, p)),
    "brier": lambda y, p: float(brier_score_loss(y, p)),
    "ece": ece,
    "expected_cost": expected_cost,
}


def bootstrap(
    y: np.ndarray, p: np.ndarray, metric: Callable[[np.ndarray, np.ndarray], float], seed: int = SEED
) -> dict[str, Any]:
    """Point estimate and percentile 95% interval; undefined replicates are counted."""
    rng = np.random.default_rng(seed)
    draws, undefined = [], 0
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) < 2:
            undefined += 1
            continue
        draws.append(metric(y[i], p[i]))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"estimate": metric(y, p), "ci95": [float(lo), float(hi)], "undefined_replicates": undefined}


def paired_difference(
    y: np.ndarray, a: np.ndarray, b: np.ndarray, metric: Callable[[np.ndarray, np.ndarray], float]
) -> dict[str, Any]:
    """metric(b) - metric(a) with a paired bootstrap interval (same rows for both)."""
    return bootstrap(y, np.stack([a, b]).T, lambda yy, pp: metric(yy, pp[:, 1]) - metric(yy, pp[:, 0]))


def summarise(y: np.ndarray, oof: np.ndarray) -> dict[str, Any]:
    pooled = oof.mean(axis=0)
    out: dict[str, Any] = {}
    for name, fn in METRICS.items():
        per_repeat = [fn(y, row) for row in oof]
        out[name] = bootstrap(y, pooled, fn) | {"repeat_range": [float(min(per_repeat)), float(max(per_repeat))]}
    return out


def baselines(y: np.ndarray) -> dict[str, float]:
    return {
        "approve_everyone": expected_cost(y, np.zeros(len(y))),
        "decline_everyone": expected_cost(y, np.ones(len(y))),
    }


def reliability(y: np.ndarray, p: np.ndarray, bins: int = ECE_BINS) -> list[dict[str, float]]:
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return [
        {"bin": b, "n": int(m.sum()), "mean_predicted": float(p[m].mean()), "observed": float(y[m].mean())}
        for b in range(bins)
        if (m := idx == b).any()
    ]
