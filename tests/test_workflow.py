from __future__ import annotations

import threading
from typing import Any

import pytest

from credit import workflow
from credit.pipeline.model import CreditModel
from credit.store import Conflict, Store
from credit.workflow import Action, IllegalAction, InvalidAction, Status


def _first(store: Store, model: CreditModel, band: str) -> dict[str, Any]:
    for row in store.all():
        if row["status"] == Status.QUEUED:
            started = workflow.start(store, model, row["id"])
            if started["record"].get("recommendation") == band:
                return started
    raise AssertionError(f"no {band} case in the queue")


def test_unknown_id(store: Store, model: CreditModel) -> None:
    with pytest.raises(workflow.NotFound):
        workflow.start(store, model, "APP-999")


def test_approve_band_is_auto_recorded(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "approve")
    assert row["status"] == Status.RECORDED
    assert row["record"]["final"] == row["record"]["final"] | {
        "decision": "approved",
        "actor": "policy",
        "auto": True,
    }
    assert "notice" not in row["record"]


def test_double_start_conflicts(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "decline")
    with pytest.raises(Conflict):
        workflow.start(store, model, row["id"])


def test_concurrent_starts_yield_exactly_one_winner(store: Store, model: CreditModel) -> None:
    app_id = store.all()[0]["id"]
    outcomes: list[str] = []

    def go() -> None:
        try:
            workflow.start(store, model, app_id)
            outcomes.append("ok")
        except Conflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["conflict"] * 3 + ["ok"]


def test_confirm_decline_records_verified_notice(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "decline")
    assert row["record"]["verification"]["passed"]
    done = workflow.act(store, row["id"], Action(action="confirm_decline", expected_revision=row["revision"]))
    assert done["status"] == Status.RECORDED
    assert done["record"]["final"]["decision"] == "declined"
    assert done["record"]["recommendation"] == "decline"


def test_stale_revision_conflicts(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "decline")
    with pytest.raises(Conflict):
        workflow.act(store, row["id"], Action(action="confirm_decline", expected_revision=row["revision"] - 1))


def test_override_needs_a_comment_and_keeps_the_recommendation(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "decline")
    with pytest.raises(InvalidAction):
        workflow.act(store, row["id"], Action(action="approve", expected_revision=row["revision"]))
    done = workflow.act(
        store,
        row["id"],
        Action(action="approve", expected_revision=row["revision"], comment="verified income"),
    )
    assert done["record"]["final"]["overrode_recommendation"] is True
    assert done["record"]["recommendation"] == "decline"


def test_refer_needs_prepare_before_decline(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "refer")
    with pytest.raises(IllegalAction):
        workflow.act(store, row["id"], Action(action="confirm_decline", expected_revision=row["revision"]))
    prepared = workflow.act(store, row["id"], Action(action="prepare_decline", expected_revision=row["revision"]))
    assert prepared["status"] == Status.NEEDS_REVIEW
    assert prepared["record"]["verification"]["passed"]
    done = workflow.act(store, row["id"], Action(action="confirm_decline", expected_revision=prepared["revision"]))
    assert done["record"]["final"]["decision"] == "declined"
    assert done["record"]["recommendation"] == "refer"


def test_variant_change_is_reverified(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "decline")
    code = row["record"]["reasons"][0]["code"]
    changed = workflow.act(
        store,
        row["id"],
        Action(action="set_variants", expected_revision=row["revision"], variants={code: "plain"}),
    )
    assert changed["record"]["notice"]["reasons"][0]["variant"] == "plain"
    assert changed["record"]["verification"]["passed"]
    assert changed["record"]["verification"]["notice_sha256"] != row["record"]["verification"]["notice_sha256"]
    with pytest.raises(InvalidAction):
        workflow.act(
            store,
            row["id"],
            Action(action="set_variants", expected_revision=changed["revision"], variants={"R99": "plain"}),
        )


def test_tampered_notice_cannot_be_sent(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "decline")
    record = dict(row["record"])
    record["notice"] = record["notice"] | {"application_id": "tampered"}
    store.transition(row["id"], [Status.NEEDS_REVIEW], row["revision"], Status.NEEDS_REVIEW, record, [])
    with pytest.raises(IllegalAction):
        workflow.act(store, row["id"], Action(action="confirm_decline", expected_revision=row["revision"] + 1))


def test_recorded_case_accepts_no_more_actions(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "approve")
    with pytest.raises(IllegalAction):
        workflow.act(store, row["id"], Action(action="approve", expected_revision=row["revision"]))


def test_failure_is_recorded_and_retryable(store: Store, model: CreditModel, monkeypatch: pytest.MonkeyPatch) -> None:
    app_id = store.all()[0]["id"]

    def boom(*_: object) -> None:
        raise RuntimeError("model exploded")

    monkeypatch.setattr(workflow, "score", boom)
    with pytest.raises(RuntimeError):
        workflow.start(store, model, app_id)
    failed = store.get(app_id)
    assert failed is not None and failed["status"] == Status.FAILED
    assert failed["record"]["error"] == "model exploded"
    monkeypatch.undo()
    assert workflow.start(store, model, app_id)["status"] in (Status.RECORDED, Status.NEEDS_REVIEW)


def test_events_are_an_audit_trail(store: Store, model: CreditModel) -> None:
    row = _first(store, model, "decline")
    kinds = [e["kind"] for e in store.events(row["id"])]
    assert kinds[:3] == ["started", "scored", "reasons_derived"]
    assert kinds[-1] == "awaiting_review"
