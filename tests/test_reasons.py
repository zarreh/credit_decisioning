from __future__ import annotations

import pandas as pd
import pytest

from credit.pipeline.attributes import CATEGORY_LABELS, EXCLUDED
from credit.pipeline.data import to_frame
from credit.pipeline.model import CreditModel
from credit.pipeline.reasons import MAX_REASONS, catalogue, contributions, principal_reasons
from credit.pipeline.scoring import score
from tests.conftest import application_of

# Author-reviewed expectations (single author, 2026-10-29; docs/decisions/0012-fixtures.md).
# Each was checked by reading the applicant's fields against the contribution table:
# the order follows contribution size and every code names a field the applicant has.
# A model change that moves any of these must be reviewed, never silently re-pinned.
CANONICAL = {
    "uci-0001": ["R01", "R02", "R06", "R03"],  # 0-200 DM checking, 48 months, <100 DM savings
    "uci-0236": ["R05", "R01", "R04", "R03"],  # 14,555 DM requested ranks first
    "uci-0605": ["R01", "R03", "R12", "R08"],  # 'all paid back duly' is adverse: dataset quirk
    "uci-0565": ["R01", "R13", "R02", "R06"],  # renting ranks second
    "uci-0127": ["R01", "R06", "R04", "R03"],  # repairs purpose
    "uci-0387": ["R01", "R06", "R05", "R12"],  # store instalment plans
    "uci-0935": ["R01", "R07", "R02", "R11"],  # under 1 year employed; no property
    "uci-0616": ["R02", "R01", "R05", "R11"],  # 60-month term ranks first
}


def test_contributions_sum_to_logit_difference(benchmark: pd.DataFrame, model: CreditModel) -> None:
    lr = model.pipeline.named_steps["lr"]
    reference_logit = float(model.coefficients() @ model.reference + lr.intercept_[0])
    for i in range(0, 1000, 37):
        row = benchmark.iloc[[i]]
        total = sum(contributions(model, row).values())
        assert total == pytest.approx(float(model.logit(row)[0]) - reference_logit, abs=1e-9)


def test_reasons_are_adverse_ordered_and_capped() -> None:
    reasons = principal_reasons({"duration_months": 0.5, "purpose": 0.9, "savings": -0.2, "job": 0.0})
    assert [r.attribute for r in reasons] == ["purpose", "duration_months"]
    many = {a: 1.0 for a in catalogue()["reasons"]}
    assert len(principal_reasons(many)) == MAX_REASONS


def test_ties_break_by_attribute_name() -> None:
    reasons = principal_reasons({"savings": 0.3, "housing": 0.3, "job": 0.3})
    assert [r.attribute for r in reasons] == ["housing", "job", "savings"]


def test_no_adverse_contribution_means_no_reasons() -> None:
    assert principal_reasons({"savings": -0.1, "job": 0.0}) == []


def test_catalogue_never_maps_a_protected_attribute() -> None:
    assert not set(catalogue()["reasons"]) & set(EXCLUDED)
    codes = [e["code"] for e in catalogue()["reasons"].values()]
    assert len(codes) == len(set(codes))


def test_catalogue_slots_render_for_every_code() -> None:
    for attribute, entry in catalogue()["reasons"].items():
        for text in entry["variants"].values():
            values = {
                s: next(iter(CATEGORY_LABELS[s].values())) if s in CATEGORY_LABELS else "1" for s in entry["slots"]
            }
            assert text.format(**values), attribute


@pytest.mark.parametrize("row_id", sorted(CANONICAL))
def test_canonical_reasons(benchmark: pd.DataFrame, model: CreditModel, row_id: str) -> None:
    scored = score(application_of(benchmark, row_id), model)
    assert [r.code for r in scored.reasons] == CANONICAL[row_id]


def test_excluded_fields_do_not_change_score_or_reasons(benchmark: pd.DataFrame, model: CreditModel) -> None:
    """Wiring guard, not a fairness claim: flipping excluded fields changes nothing."""
    flips = {"personal_status_sex": "A92", "age_years": 70, "foreign_worker": "A202", "telephone": "A192"}
    for row_id in ["uci-0001", "uci-0010", "uci-0100", "uci-0500"]:
        original = application_of(benchmark, row_id)
        flipped = original.model_copy(update=flips)
        a, b = score(original, model), score(flipped, model)
        assert a.score.p_bad == b.score.p_bad
        assert a.reasons == b.reasons
        assert to_frame(original).shape == to_frame(flipped).shape
