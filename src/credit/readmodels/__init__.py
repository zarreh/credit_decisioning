"""Read-only views over the evidence, the review queue and the benchmark.

Used by the API and by the analyst's tools. Nothing here writes, and nothing here
returns a protected attribute for an individual: the analyst sees applicants only
through ``case_view``, which drops them, and sees groups only through suppressed
aggregates (n < 30 is never returned as a number).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from credit.pipeline.attributes import CATEGORY_LABELS, EXCLUDED, MODEL_FEATURES, MODEL_NUMERIC
from credit.pipeline.data import load
from credit.store import Store

MIN_CELL_N = 30


class QueryError(ValueError):
    """A request the read models refuse (unknown field, protected attribute, ...)."""


@lru_cache
def evidence(path: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def evidence_all(path: str) -> dict[str, Any]:
    """Everything about model quality in one result: both models' four metrics with CIs,
    the paired differences, the trivial baselines, the policy and the provenance. One call
    answers any performance question, so the agent has no reason to fan out."""
    e = evidence(path)
    return {
        "source_id": "evidence",
        "champion": e["champion"],
        "challenger": e["challenger"],
        "challenger_minus_champion": e["challenger_minus_champion"],
        "baselines": e["baselines"],
        "policy": e["policy"],
        "provenance": e["provenance"],
        "glossary": {
            "auroc": "ranking quality; 0.5 is a coin flip",
            "expected_cost": "average cost per applicant under the 5:1 cost matrix; lower is better",
            "brier": "mean squared error of the probabilities; lower is better",
            "ece": "calibration error; lower is better",
        },
    }


def fairness(path: str, attribute: Literal["sex", "foreign_worker", "age_band"]) -> dict[str, Any]:
    e = evidence(path)
    return {
        "source_id": f"fairness:{attribute}",
        "rows": e["fairness"][attribute],
        "proxy_audit": e["proxy_audit"][attribute],
        "note": "Measure and disclose; the 80% adverse-impact ratio is a screening heuristic, not a legal test.",
        "small_n_rule": (
            f"A group with fewer than {MIN_CELL_N} applicants, or fewer than 10 of either outcome, is reported as "
            "insufficient n with no point estimate."
        ),
    }


def case_view(store: Store, app_id: str) -> dict[str, Any]:
    row = store.get(app_id)
    if row is None:
        raise QueryError(f"no application {app_id}")
    application = {
        k: CATEGORY_LABELS[k][v] if k in CATEGORY_LABELS else v
        for k, v in row["application"].items()
        if k not in EXCLUDED
    }
    record = row["record"]
    return {
        "source_id": f"case:{app_id}",
        "id": app_id,
        "status": row["status"],
        "application": application,
        "p_bad": record.get("score", {}).get("p_bad"),
        "recommendation": record.get("recommendation"),
        "reasons": record.get("reasons", []),
        "verification": record.get("verification"),
        "final": record.get("final"),
        "events": [{"kind": e["kind"], "actor": e["actor"], "at": e["at"]} for e in store.events(app_id)],
    }


def queue_summary(store: Store) -> dict[str, Any]:
    rows = store.all()
    by_status: dict[str, int] = {}
    by_recommendation: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        rec = r["record"].get("recommendation", "not scored")
        by_recommendation[rec] = by_recommendation.get(rec, 0) + 1
    return {
        "source_id": "queue:summary",
        "total": len(rows),
        "by_status": by_status,
        "by_recommendation": by_recommendation,
        "ids_needing_review": [r["id"] for r in rows if r["status"] == "needs_review"],
    }


@lru_cache
def _benchmark() -> pd.DataFrame:
    return load()


def benchmark_aggregate(
    metric: Literal["count", "bad_rate", "mean"],
    group_by: str | None = None,
    value_column: str | None = None,
    filters: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Allowlisted aggregate over the 1,000 benchmark rows. No raw rows, no SQL."""
    allowed = set(MODEL_FEATURES)
    for column in [group_by, value_column, *(filters or {})]:
        if column is not None and column not in allowed:
            hint = " Age, sex, foreign-worker status and telephone are protected: use get_fairness_table."
            raise QueryError(f"{column} is not queryable; allowed: {sorted(allowed)}.{hint}")
    for column, codes in (filters or {}).items():
        valid = CATEGORY_LABELS.get(column)
        if valid is None:
            raise QueryError(f"{column} is numeric; filters take category columns with UCI codes")
        unknown = [c for c in codes if c not in valid]
        if unknown:
            raise QueryError(f"unknown {column} code(s) {unknown}; valid codes: {valid}")
    if metric == "mean" and value_column not in MODEL_NUMERIC:
        raise QueryError(f"mean needs a numeric value_column from {list(MODEL_NUMERIC)}")
    frame = _benchmark()
    for column, codes in (filters or {}).items():
        frame = frame[frame[column].isin(codes)]
    groups = frame.groupby(group_by) if group_by else [("all", frame)]
    cells = []
    for key, part in groups:
        label = CATEGORY_LABELS.get(group_by or "", {}).get(str(key), str(key))
        cell: dict[str, Any] = {"group": label, "code": str(key), "n": int(len(part))}
        if len(part) < MIN_CELL_N:
            cell["value"], cell["suppressed"] = None, True
        elif metric == "count":
            cell["value"] = int(len(part))
        elif metric == "bad_rate":
            cell["value"] = round(float(part["bad"].mean()), 4)
        else:
            cell["value"] = round(float(part[value_column].mean()), 4)
        cells.append(cell)
    query = {"metric": metric, "group_by": group_by, "value_column": value_column, "filters": filters}
    return {
        "source_id": "benchmark:" + json.dumps(query, sort_keys=True),
        "query": query,
        "cells": cells,
        "note": (
            f"UCI benchmark, n = {len(frame)} after filters. Cells with n < {MIN_CELL_N} are suppressed on "
            "purpose (value null); report them as suppressed and do not try to work around it."
        ),
    }
