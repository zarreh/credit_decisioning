"""Protected-group audit and proxy audit: measure and disclose, never certify (§4).

Runs on pooled out-of-fold predictions at the binary threshold. A group with fewer
than 30 applicants, or fewer than 10 of either outcome, is reported as
``insufficient_n`` with no point estimate: a visible gap, not an omitted row.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

from credit.pipeline.attributes import MODEL_FEATURES
from credit.pipeline.evaluate import N_BOOT, bootstrap, expected_cost
from credit.pipeline.model import SEED, preprocess
from credit.pipeline.policy import THRESHOLD

MIN_GROUP_N, MIN_CLASS_N = 30, 10


def audit_groups(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Audit group labels per protected attribute.

    Sex: UCI code A92 is the only female code present (A95 never occurs), and it mixes
    marital statuses, so only female/male is supported. Foreign worker is a crude
    national-origin proxy. Age 62+ is reported separately as a known gap.
    """
    age = frame["age_years"]
    return {
        "sex": frame["personal_status_sex"].map(lambda c: "female" if c in {"A92", "A95"} else "male"),
        "foreign_worker": frame["foreign_worker"].map({"A201": "yes", "A202": "no"}),
        "age_band": pd.cut(age, [0, 24, 39, 61, 200], labels=["under 25", "25-39", "40-61", "62+"]).astype(str),
    }


def sufficient(y: np.ndarray) -> bool:
    return len(y) >= MIN_GROUP_N and min(int(y.sum()), int(len(y) - y.sum())) >= MIN_CLASS_N


def _rates(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    decline = p > THRESHOLD
    return {
        "approval_rate": float((~decline).mean()),
        "false_positive_rate": float(decline[y == 0].mean()),
        "false_negative_rate": float((~decline)[y == 1].mean()),
        "calibration_gap": float(p.mean() - y.mean()),
        "expected_cost": expected_cost(y, p),
    }


def _group_ci(y: np.ndarray, p: np.ndarray, seed: int) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    draws: dict[str, list[float]] = {}
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if not sufficient(y[i]):
            continue
        for k, v in _rates(y[i], p[i]).items():
            draws.setdefault(k, []).append(v)
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items()}


def fairness_table(frame: pd.DataFrame, pooled: np.ndarray) -> dict[str, Any]:
    y = frame["bad"].to_numpy()
    out: dict[str, Any] = {}
    for attribute, groups in audit_groups(frame).items():
        rows: list[dict[str, Any]] = []
        for k, name in enumerate(sorted(groups.unique())):
            mask = (groups == name).to_numpy()
            gy, gp = y[mask], pooled[mask]
            row: dict[str, Any] = {"group": name, "n": int(mask.sum()), "n_bad": int(gy.sum())}
            if sufficient(gy):
                row |= {"status": "ok", **_rates(gy, gp), "ci95": _group_ci(gy, gp, SEED + k)}
            else:
                row |= {"status": "insufficient_n"}
            rows.append(row)
        rated = [r["approval_rate"] for r in rows if r["status"] == "ok"]
        top = max(rated) if rated else 0.0
        for r in rows:
            if r["status"] == "ok":
                r["adverse_impact_ratio"] = r["approval_rate"] / top if top > 0 else None
        out[attribute] = rows
    return out


def _macro_auc(k: int) -> Callable[[np.ndarray, np.ndarray], float]:
    def metric(t: np.ndarray, s: np.ndarray) -> float:
        if len(np.unique(t)) < k:
            return float("nan")
        return float(roc_auc_score(t, s, multi_class="ovr", average="macro", labels=list(range(k))))

    return metric


def proxy_audit(frame: pd.DataFrame) -> dict[str, Any]:
    """How well the permitted features predict each excluded attribute (CV AUROC)."""
    out: dict[str, Any] = {}
    X = frame[list(MODEL_FEATURES)]
    for attribute, groups in audit_groups(frame).items():
        target = groups.to_numpy()
        counts = pd.Series(target).value_counts()
        keep = np.isin(target, counts[counts >= MIN_GROUP_N].index)
        classes = sorted(set(target[keep]))
        model = Pipeline([("prep", preprocess()), ("lr", LogisticRegression(max_iter=2000))])
        cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
        proba = cross_val_predict(model, X[keep], target[keep], cv=cv, method="predict_proba")
        codes = np.searchsorted(classes, target[keep])
        if len(classes) == 2:
            result = bootstrap(codes, proba[:, 1], lambda t, s: float(roc_auc_score(t, s)))
        else:
            result = bootstrap(codes, proba, _macro_auc(len(classes)))
        out[attribute] = {
            "auroc": result,
            "classes": {c: int(counts[c]) for c in counts.index},
            "excluded_small_classes": [c for c in counts.index if counts[c] < MIN_GROUP_N],
            "method": "binary" if len(classes) == 2 else "macro one-vs-rest",
        }
    return out
