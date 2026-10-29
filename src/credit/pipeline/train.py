"""``make train``: evaluate champion and challenger, audit fairness, fit the serving model.

Writes ``artifacts/model.joblib`` (the serving champion, fitted on all 1,000 rows only
after evaluation) and ``artifacts/evidence.json`` (every published number, with its
n, label source, scorer, model version, run date and uncertainty; §9.5).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn

from credit.pipeline import evaluate as ev
from credit.pipeline.data import CITATION, SOURCE_SHA256, load
from credit.pipeline.fairness import fairness_table, proxy_audit
from credit.pipeline.model import SEED, challenger, champion, fit_champion
from credit.pipeline.policy import COST_APPROVE_BAD, COST_DECLINE_GOOD, REFER_CEILING, THRESHOLD, band

MODEL_VERSION = "champion-lr-sigmoid-v1"
ARTIFACTS = Path("artifacts")


def build_evidence() -> tuple[dict[str, Any], Any]:
    frame = load()
    y = frame["bad"].to_numpy()
    champ_oof, chall_oof = ev.oof_predictions(frame, champion), ev.oof_predictions(frame, challenger)
    pooled, pooled_chall = champ_oof.mean(axis=0), chall_oof.mean(axis=0)
    served = fit_champion(frame, MODEL_VERSION)
    bands = [band(float(p)).value for p in pooled]
    evidence = {
        "provenance": {
            "n": len(frame),
            "n_bad": int(y.sum()),
            "label_source": "UCI Statlog German Credit labels (1994), recoded 2 = bad",
            "scorer": "deterministic code (scikit-learn metrics on pooled out-of-fold predictions)",
            "model_version": MODEL_VERSION,
            "run_date": datetime.now(UTC).date().isoformat(),
            "uncertainty": f"percentile bootstrap, {ev.N_BOOT} row resamples, 95%",
            "validation": f"repeated stratified {ev.N_SPLITS}-fold CV x {ev.N_REPEATS}, seed {SEED}",
            "data_sha256": SOURCE_SHA256,
            "citation": CITATION,
            "sklearn": sklearn.__version__,
        },
        "policy": {
            "cost_approve_bad": COST_APPROVE_BAD,
            "cost_decline_good": COST_DECLINE_GOOD,
            "threshold": THRESHOLD,
            "refer_ceiling": REFER_CEILING,
            "band_counts": {b: bands.count(b) for b in ("approve", "refer", "decline")},
        },
        "baselines": ev.baselines(y),
        "champion": ev.summarise(y, champ_oof),
        "challenger": ev.summarise(y, chall_oof),
        "challenger_minus_champion": {
            "auroc": ev.paired_difference(y, pooled, pooled_chall, ev.METRICS["auroc"]),
            "expected_cost": ev.paired_difference(y, pooled, pooled_chall, ev.expected_cost),
        },
        "reliability": ev.reliability(y, pooled),
        "fairness": fairness_table(frame, pooled),
        "proxy_audit": proxy_audit(frame),
        "serving_model": {
            "version": MODEL_VERSION,
            "fitted_on_n": len(frame),
            "reference_kind": served.reference_kind,
            "reference_n": served.reference_n,
            "calibration_slope": float(served.calibrated.calibrated_classifiers_[0].calibrators[0].a_),
        },
    }
    return evidence, served


def _round(value: Any) -> Any:
    if isinstance(value, float | np.floating):
        return round(float(value), 6)
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v) for v in value]
    return value


def main() -> None:
    evidence, served = build_evidence()
    ARTIFACTS.mkdir(exist_ok=True)
    joblib.dump(served, ARTIFACTS / "model.joblib")
    (ARTIFACTS / "evidence.json").write_text(json.dumps(_round(evidence), indent=2) + "\n")
    c = evidence["champion"]["expected_cost"]
    print(f"champion expected cost {c['estimate']:.3f} {c['ci95']}; baselines {evidence['baselines']}")


if __name__ == "__main__":
    main()
