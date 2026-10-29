from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from credit.pipeline.attributes import EXCLUDED, MODEL_FEATURES
from credit.pipeline.data import DataIntegrityError, parse
from credit.pipeline.evaluate import baselines, ece, expected_cost
from credit.pipeline.fairness import sufficient
from credit.pipeline.model import fit_champion
from credit.pipeline.policy import THRESHOLD, band, decline_threshold
from credit.schemas import Band


def test_benchmark_shape_and_label_recoding(benchmark: pd.DataFrame) -> None:
    assert len(benchmark) == 1000
    assert int(benchmark["bad"].sum()) == 300
    assert benchmark["row_id"].is_unique


def test_class_two_means_bad() -> None:
    row = "A11 6 A34 A43 1169 A65 A75 4 A93 A101 4 A121 67 A143 A152 2 A173 1 A192 A201 {}"
    frame = parse("\n".join([row.format(1), row.format(2)]))
    assert frame["bad"].tolist() == [0, 1]


def test_unknown_code_is_rejected() -> None:
    bad = "A19 6 A34 A43 1169 A65 A75 4 A93 A101 4 A121 67 A143 A152 2 A173 1 A192 A201 1"
    with pytest.raises(DataIntegrityError):
        parse(bad)


def test_protected_attributes_are_not_model_inputs() -> None:
    assert not set(EXCLUDED) & set(MODEL_FEATURES)
    assert {"personal_status_sex", "age_years", "foreign_worker", "telephone"} == set(EXCLUDED)


def test_threshold_is_derived_from_costs() -> None:
    assert pytest.approx(1 / (1 + 5)) == THRESHOLD
    assert decline_threshold(cost_approve_bad=3, cost_decline_good=1) == pytest.approx(0.25)


def test_bands_and_tie_goes_to_review() -> None:
    assert band(THRESHOLD - 1e-9) is Band.APPROVE
    assert band(THRESHOLD) is Band.REFER
    assert band(0.25) is Band.REFER
    assert band(0.2500001) is Band.DECLINE


def test_trivial_baselines() -> None:
    y = np.array([1] * 300 + [0] * 700)
    assert baselines(y) == {"approve_everyone": 1.5, "decline_everyone": 0.7}
    assert expected_cost(y, y.astype(float)) == 0.0


def test_ece_is_zero_when_perfectly_calibrated_bins() -> None:
    y = np.array([0, 1, 0, 1])
    assert ece(y, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.0)


def test_small_n_rule() -> None:
    assert not sufficient(np.array([1] * 5 + [0] * 40))
    assert not sufficient(np.array([1] * 12 + [0] * 12))
    assert sufficient(np.array([1] * 10 + [0] * 20))


def test_fit_uses_training_rows_only(benchmark: pd.DataFrame) -> None:
    """Leakage guard: perturbing held-out rows cannot change the fitted model."""
    train, held_out = benchmark.iloc[:800], benchmark.iloc[800:].copy()
    first = fit_champion(train, "t")
    held_out["credit_amount"] = held_out["credit_amount"] * 50
    second = fit_champion(train, "t")
    np.testing.assert_allclose(first.coefficients(), second.coefficients())
    np.testing.assert_allclose(first.reference, second.reference)
    assert first.reference_n >= 50
