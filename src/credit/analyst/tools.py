"""The analyst's tools. All read-only except ``save_report_draft``, which writes only a
draft row (never decision data) and runs only after a human approves it (HITL).

Every tool returns JSON with a ``source_id`` that the answer's claims must cite.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool

from credit import readmodels as rm
from credit.store import Store


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def build_tools(store: Store, evidence_path: str) -> list[BaseTool]:
    @tool
    def get_evidence() -> str:
        """All model-quality evidence in ONE call: champion and challenger AUROC, expected cost,
        Brier and ECE with 95% CIs, the champion-vs-challenger differences, the trivial baselines
        (approve everyone, decline everyone), the decision policy (costs, threshold, band counts)
        and the data provenance (n, scorer, run date). Call it once for any performance question."""
        return _json(rm.evidence_all(evidence_path))

    @tool
    def get_fairness_table(attribute: Literal["sex", "foreign_worker", "age_band"]) -> str:
        """Approval rate, adverse-impact ratio, error rates and calibration gap per group,
        with CIs, plus the proxy audit for that attribute. Small groups are suppressed."""
        return _json(rm.fairness(evidence_path, attribute))

    @tool
    def get_case(case_id: str) -> str:
        """One application in the review queue (e.g. 'APP-007'): its fields (protected
        attributes removed), score, recommendation, reasons, verifier checks, events and
        final decision."""
        return _json(rm.case_view(store, case_id))

    @tool
    def get_queue_summary() -> str:
        """Counts of queue applications by status and by model recommendation."""
        return _json(rm.queue_summary(store))

    @tool
    def query_benchmark(
        metric: Literal["count", "bad_rate", "mean"],
        group_by: str | None = None,
        value_column: str | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> str:
        """Aggregate over the 1,000 benchmark rows: count, bad_rate or mean (mean needs a numeric
        value_column such as duration_months or credit_amount). group_by / filters take model
        feature names (e.g. 'purpose', 'checking_status') and UCI codes (e.g. {'purpose': ['A40']}).
        Each result cell has the group label, its code and n. Age, sex, foreign worker and
        telephone are not queryable. Cells with n < 30 are suppressed (value null): report them as
        suppressed, never work around it."""
        return _json(rm.benchmark_aggregate(metric, group_by, value_column, filters))

    @tool
    def save_report_draft(kind: Literal["queue", "model_risk", "fairness"], title: str, body: str) -> str:
        """Save a report as a DRAFT for a human to review. Requires human approval before
        it runs. Never sends anything anywhere."""
        draft_id = store.add_draft(kind, title, body)
        return _json({"source_id": f"draft:{draft_id}", "draft_id": draft_id, "status": "draft"})

    return [
        get_evidence,
        get_fairness_table,
        get_case,
        get_queue_summary,
        query_benchmark,
        save_report_draft,
    ]
