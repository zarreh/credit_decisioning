from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from credit.analyst.grounding import check, numbers_in
from credit.analyst.middleware import AnswerPush
from credit.analyst.schemas import Claim
from credit.readmodels import QueryError, benchmark_aggregate, case_view
from credit.store import Store
from evals.analyst import CASES, run_case

SRC = {
    "evidence": {
        "champion": {"auroc": {"estimate": 0.779976, "ci95": [0.750584, 0.809789]}},
        "provenance": {"n": 1000},
    },
    "fairness:age_band": {"rows": [{"group": "62+", "n": 38, "approval_rate": None}, {"group": "under 25", "n": 149}]},
    "benchmark": {"cells": [{"group": "0 to 200 DM", "code": "A12", "n": 269}]},
}
EST = Claim(value=0.78, source_id="evidence", field="champion.auroc.estimate")


def test_number_tokens_skip_ids_dates_and_list_markers_but_split_ranges() -> None:
    assert numbers_in("APP-012 on 2026-10-29: 0.75-0.81, 1,000 rows, 34%") == ["0.75", "0.81", "1,000", "34%"]
    assert numbers_in("1. first 0.5\n2) second 7\n  3. third") == ["0.5", "7"]


@pytest.mark.parametrize(
    ("text", "ok"),
    [("AUROC 0.78", True), ("AUROC 78%", True), ("AUROC 0.780", True), ("AUROC 0.781", False), ("AUROC 1", False)],
)
def test_text_is_checked_against_tool_values_at_display_precision(text: str, ok: bool) -> None:
    assert check(text, [EST], SRC).verified is ok


def test_whole_numbers_must_match_exactly_but_percentages_may_round() -> None:
    assert check("n = 1,000", [], SRC).verified
    assert not check("n = 999", [], SRC).verified
    assert check("about 78%", [], SRC).verified  # 77.9976 rounds to 78
    assert not check("about 79%", [], SRC).verified


def test_numbers_inside_tool_strings_can_be_quoted() -> None:
    assert check("The 0 to 200 DM group has 269 applicants (code A12).", [], SRC).verified
    assert not check("The group has 270 applicants.", [], SRC).verified


def test_numbers_missing_from_the_tool_results_fail() -> None:
    assert not check("AUROC 0.78 on 1,200 rows", [EST], SRC).verified


def test_suppressed_cells_cannot_be_found() -> None:
    result = check("62+ approval is 0.40", [], SRC)
    assert not result.verified and "0.40" in result.problems[0]


def test_citation_problems_are_reported_but_do_not_decide() -> None:
    bad_source = EST.model_copy(update={"source_id": "nope"})
    result = check("AUROC 0.78", [bad_source], SRC)
    assert result.verified and "never retrieved" in result.citation_problems[0]
    wrong_field = Claim(value=0.78, source_id="evidence", field="provenance.n")
    assert check("AUROC 0.78", [wrong_field], SRC).citation_problems
    assert not check("AUROC 0.78", [EST], SRC).citation_problems


def test_path_glued_onto_the_source_id_is_resolved() -> None:
    glued = Claim(value=0.78, source_id="evidence.champion.auroc.estimate", field="")
    assert not check("AUROC 0.78", [glued], SRC).citation_problems


def test_exempt_numbers() -> None:
    assert check("95% CI on the 1994 data", [], SRC).verified
    assert check("You asked about APP-7 and 12 months", [], SRC, exempt=[12]).verified


def test_benchmark_refuses_protected_and_suppresses_small_cells() -> None:
    with pytest.raises(QueryError, match="get_fairness_table"):
        benchmark_aggregate("bad_rate", group_by="age_years")
    with pytest.raises(QueryError, match="valid codes"):
        benchmark_aggregate("count", filters={"purpose": ["new car"]})
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


class _Request:
    def __init__(self, messages: list[object], tools: list[str]) -> None:
        self.messages, self.tools = messages, tools

    def override(self, **changes: object) -> _Request:
        return _Request(changes.get("messages", self.messages), changes.get("tools", self.tools))  # type: ignore[arg-type]


def _tool_round(name: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": f"c-{name}"}])


def test_answer_push_removes_tools_after_enough_rounds() -> None:
    push = AnswerPush(max_rounds=2)
    seen: list[_Request] = []

    def handler(request: object) -> str:
        seen.append(request)  # type: ignore[arg-type]
        return "ok"

    one = [HumanMessage(content="q"), _tool_round("get_evidence")]
    push.wrap_model_call(_Request(one, ["t"]), handler)  # type: ignore[arg-type]
    assert seen[-1].tools == ["t"]
    two = [*one, ToolMessage(content="{}", tool_call_id="c-get_evidence"), _tool_round("get_case")]
    push.wrap_model_call(_Request(two, ["t"]), handler)  # type: ignore[arg-type]
    assert seen[-1].tools == [] and "final answer" in str(seen[-1].messages[-1].content)  # type: ignore[attr-defined]


def test_answer_push_counts_only_the_current_turn_and_ignores_the_answer_tool() -> None:
    older = [HumanMessage(content="old"), _tool_round("a"), _tool_round("b"), _tool_round("c")]
    now = [*older, HumanMessage(content="new"), _tool_round("AnalystAnswer")]
    assert AnswerPush.rounds(now) == 0
    assert AnswerPush.rounds(older) == 3


def test_fairness_result_states_its_small_n_rule_so_the_number_can_be_quoted() -> None:
    from credit.readmodels import fairness

    result = fairness("artifacts/evidence.json", "age_band")
    assert check("Groups with fewer than 30 applicants are suppressed.", [], {result["source_id"]: result}).verified
