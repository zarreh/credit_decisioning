from __future__ import annotations

import pytest

from credit.analyst.grounding import check, numbers_in
from credit.analyst.schemas import Claim
from credit.readmodels import QueryError, benchmark_aggregate, case_view
from credit.store import Store
from evals.analyst import CASES, run_case

SRC = {"evidence:champion.auroc": {"estimate": 0.779976, "ci95": [0.750584, 0.809789], "n": 1000}}
EST = Claim(value=0.78, source_id="evidence:champion.auroc", field="estimate")


def test_number_tokens_skip_ids_and_dates_but_split_ranges() -> None:
    assert numbers_in("APP-012 on 2026-10-29: 0.75-0.81, 1,000 rows, 34%") == ["0.75", "0.81", "1,000", "34%"]


@pytest.mark.parametrize(
    ("text", "ok"), [("AUROC 0.78", True), ("AUROC 78%", True), ("AUROC 0.780", True), ("AUROC 0.781", False)]
)
def test_text_is_checked_against_the_source_at_display_precision(text: str, ok: bool) -> None:
    assert check(text, [EST], SRC).verified is ok


def test_uncited_and_wrong_numbers_fail() -> None:
    assert not check("AUROC 0.78 on 1,200 rows", [EST], SRC).verified
    wrong = Claim(value=0.81, source_id="evidence:champion.auroc", field="estimate")
    assert not check("AUROC 0.81", [wrong], SRC).verified


def test_unknown_source_and_null_value_fail() -> None:
    assert not check("x 0.78", [EST.model_copy(update={"source_id": "nope"})], SRC).verified
    nulls = {"s": {"cells": [{"value": None}]}}
    assert not check("x 0.4", [Claim(value=0.4, source_id="s", field="cells.0.value")], nulls).verified


def test_exempt_numbers() -> None:
    assert check("95% CI on the 1994 data", [], SRC).verified
    assert check("You asked about APP-7 and 12 months", [], SRC, exempt=[12]).verified


def test_benchmark_refuses_protected_and_suppresses_small_cells() -> None:
    with pytest.raises(QueryError):
        benchmark_aggregate("bad_rate", group_by="age_years")
    out = benchmark_aggregate("bad_rate", group_by="purpose")
    small = [c for c in out["cells"] if c["n"] < 30]
    assert small and all(c["value"] is None and c["suppressed"] for c in small)


def test_case_view_drops_protected_fields(store: Store) -> None:
    view = case_view(store, "APP-001")
    assert not {"age_years", "personal_status_sex", "foreign_worker", "telephone"} & set(view["application"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_analyst_cases(case) -> None:  # type: ignore[no-untyped-def]
    ok, _ = run_case(case)
    assert ok
