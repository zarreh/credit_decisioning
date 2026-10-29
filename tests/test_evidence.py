from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from credit.pipeline import evaluate as ev
from credit.pipeline.fairness import audit_groups, fairness_table, proxy_audit
from credit.pipeline.model import champion
from evals.run import model_gate

ROOT = Path(__file__).resolve().parents[1]


def test_oof_gives_one_prediction_per_row_per_repeat(benchmark: pd.DataFrame) -> None:
    subset = benchmark.sample(300, random_state=1).reset_index(drop=True)
    oof = ev.oof_predictions(subset, champion)
    assert oof.shape == (ev.N_REPEATS, 300)
    assert np.all((oof > 0) & (oof < 1))
    summary = ev.summarise(subset["bad"].to_numpy(), oof)
    for metric in ("auroc", "brier", "ece", "expected_cost"):
        lo, hi = summary[metric]["ci95"]
        assert lo <= hi
        assert len(summary[metric]["repeat_range"]) == 2


def test_paired_difference_of_identical_models_is_zero() -> None:
    rng = np.random.default_rng(0)
    y, p = rng.integers(0, 2, 200), rng.random(200)
    diff = ev.paired_difference(y, p, p, ev.expected_cost)
    assert diff["estimate"] == 0 and diff["ci95"] == [0.0, 0.0]


def test_reliability_bins_cover_all_rows() -> None:
    p = np.linspace(0.01, 0.99, 100)
    assert sum(b["n"] for b in ev.reliability(np.zeros(100), p)) == 100


def test_audit_groups_follow_the_codebook(benchmark: pd.DataFrame) -> None:
    groups = audit_groups(benchmark)
    assert groups["sex"].value_counts().to_dict() == {"male": 690, "female": 310}
    assert (groups["age_band"] == "62+").sum() == 38


def test_fairness_table_suppresses_small_groups(benchmark: pd.DataFrame) -> None:
    pooled = np.full(len(benchmark), 0.1)
    table = fairness_table(benchmark, pooled)
    by_group = {r["group"]: r for r in table["age_band"]}
    assert by_group["62+"]["status"] == "insufficient_n" and "approval_rate" not in by_group["62+"]
    assert by_group["25-39"]["approval_rate"] == 1.0 and by_group["25-39"]["adverse_impact_ratio"] == 1.0


def test_proxy_audit_reports_auroc_with_interval(benchmark: pd.DataFrame) -> None:
    audit = proxy_audit(benchmark)
    for attribute in ("sex", "foreign_worker", "age_band"):
        lo, hi = audit[attribute]["auroc"]["ci95"]
        assert 0.0 <= lo <= audit[attribute]["auroc"]["estimate"] <= hi <= 1.0


def test_committed_evidence_passes_the_model_gate() -> None:
    evidence = json.loads((ROOT / "artifacts/evidence.json").read_text())
    gates = yaml.safe_load((ROOT / "evals/gates.yaml").read_text())
    assert model_gate(evidence, gates["model"]) == []
    worse = json.loads(json.dumps(evidence))
    worse["champion"]["expected_cost"]["estimate"] = 0.71
    assert len(model_gate(worse, gates["model"])) == 2


@pytest.mark.parametrize("field", ["n", "label_source", "scorer", "model_version", "run_date", "uncertainty"])
def test_evidence_states_the_six_honesty_fields(field: str) -> None:
    assert json.loads((ROOT / "artifacts/evidence.json").read_text())["provenance"][field]
