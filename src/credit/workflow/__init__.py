"""The review workflow: a plain-code state machine over the store (no LLM, no graph).

    queued ──start──► scoring ──► recorded          (approve band: auto-approved)
       ▲                 │
       └──retry── failed ◄┴──► needs_review ──approve / confirm_decline──► recorded

In ``needs_review`` a reviewer may also ``prepare_decline`` (refer band: derive reasons
and build a notice) or ``set_variants`` (choose approved wording; re-verified). The
model's recommendation and the human's final decision are stored separately (C6).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from credit.guardrails.verifier import Expected, notice_sha256, verify
from credit.notice import render_decline
from credit.pipeline.model import CreditModel
from credit.pipeline.reasons import principal_reasons
from credit.pipeline.scoring import score
from credit.schemas import Application, Band, Notice, Reason, Variant
from credit.store import Conflict, Store, now


class Status(StrEnum):
    QUEUED = "queued"
    SCORING = "scoring"
    NEEDS_REVIEW = "needs_review"
    RECORDED = "recorded"
    FAILED = "failed"


class NotFound(Exception):
    pass


class IllegalAction(Exception):
    """The action is not allowed in the application's current state."""


class InvalidAction(Exception):
    """The action is allowed here, but its inputs are incomplete (e.g. no comment)."""


class Action(BaseModel):
    action: Literal["approve", "confirm_decline", "prepare_decline", "set_variants"]
    expected_revision: int
    reviewer: str = Field(default="demo-reviewer", min_length=1, max_length=60)
    comment: str | None = Field(default=None, max_length=1000)
    variants: dict[str, Variant] | None = None


def _load(store: Store, app_id: str) -> dict[str, Any]:
    row = store.get(app_id)
    if row is None:
        raise NotFound(app_id)
    return row


def _notice_and_check(
    app_id: str, application: Application, reasons: list[Reason], variants: dict[str, Variant]
) -> dict[str, Any]:
    notice = render_decline(app_id, application, reasons, variants)
    report = verify(notice, Expected(application, [r.code for r in reasons], "declined"))
    return {"notice": notice.model_dump(mode="json"), "verification": report.model_dump(mode="json")}


def start(store: Store, model: CreditModel, app_id: str) -> dict[str, Any]:
    """Claim and score. Raises NotFound, or Conflict if already started."""
    row = _load(store, app_id)
    if row["status"] not in (Status.QUEUED, Status.FAILED):
        raise Conflict(app_id)
    store.transition(
        app_id,
        [Status.QUEUED, Status.FAILED],
        row["revision"],
        Status.SCORING,
        row["record"],
        [("started", "system", {})],
    )
    revision = row["revision"] + 1
    try:
        application = Application(**row["application"])
        scored = score(application, model)
        record: dict[str, Any] = {
            "score": scored.score.model_dump(mode="json"),
            "recommendation": scored.score.band.value,
            "reasons": [],
        }
        events: list[tuple[str, str, dict[str, Any]]] = [
            ("scored", "model", {"p_bad": scored.score.p_bad, "band": scored.score.band.value})
        ]
        if scored.score.band is Band.APPROVE:
            record["final"] = {"decision": "approved", "actor": "policy", "auto": True, "at": now()}
            events.append(("auto_approved", "policy", {}))
            store.transition(app_id, [Status.SCORING], revision, Status.RECORDED, record, events)
        else:
            if scored.score.band is Band.DECLINE:
                record["reasons"] = [r.model_dump() for r in scored.reasons]
                events.append(("reasons_derived", "code", {"codes": [r.code for r in scored.reasons]}))
                if scored.reasons:
                    record |= _notice_and_check(app_id, application, scored.reasons, {})
                    events.append(("verified", "code", {"passed": record["verification"]["passed"]}))
                else:
                    events.append(("no_reasons", "code", {"note": "manual review required"}))
            events.append(("awaiting_review", "system", {"band": scored.score.band.value}))
            store.transition(app_id, [Status.SCORING], revision, Status.NEEDS_REVIEW, record, events)
    except Exception as exc:
        store.transition(
            app_id,
            [Status.SCORING],
            revision,
            Status.FAILED,
            {"error": str(exc)},
            [("failed", "system", {"error": str(exc)})],
        )
        raise
    return _load(store, app_id)


def act(store: Store, app_id: str, action: Action) -> dict[str, Any]:
    row = _load(store, app_id)
    if row["status"] != Status.NEEDS_REVIEW:
        raise IllegalAction(f"cannot {action.action} an application that is {row['status']}")
    if action.expected_revision != row["revision"]:
        raise Conflict(app_id)
    record, application = dict(row["record"]), Application(**row["application"])
    reasons = [Reason(**r) for r in record.get("reasons", [])]
    to_status, actor = Status.NEEDS_REVIEW, action.reviewer
    events: list[tuple[str, str, dict[str, Any]]]

    if action.action == "approve":
        overrode = record["recommendation"] == Band.DECLINE
        if overrode and not (action.comment and action.comment.strip()):
            raise InvalidAction("overriding a decline recommendation needs a comment")
        record["final"] = {
            "decision": "approved",
            "actor": actor,
            "comment": action.comment,
            "overrode_recommendation": overrode,
            "at": now(),
        }
        to_status, events = Status.RECORDED, [("approved", actor, {"overrode_recommendation": overrode})]

    elif action.action == "prepare_decline":
        if record["recommendation"] != Band.REFER or "notice" in record:
            raise IllegalAction("prepare_decline applies only to a referred case without a notice")
        reasons = principal_reasons(record["score"]["contributions"])
        if not reasons:
            raise IllegalAction("no adverse reasons can be derived; this case cannot be declined with a notice")
        record["reasons"] = [r.model_dump() for r in reasons]
        record |= _notice_and_check(app_id, application, reasons, {})
        events = [
            ("reasons_derived", "code", {"codes": [r.code for r in reasons]}),
            ("verified", "code", {"passed": record["verification"]["passed"]}),
        ]

    elif action.action == "set_variants":
        if "notice" not in record:
            raise IllegalAction("there is no notice to reword")
        if not action.variants or set(action.variants) - {r.code for r in reasons}:
            raise InvalidAction("variants must name at least one of this notice's reason codes")
        record |= _notice_and_check(app_id, application, reasons, action.variants)
        events = [
            ("variants_set", actor, {"variants": action.variants}),
            ("verified", "code", {"passed": record["verification"]["passed"]}),
        ]

    else:  # confirm_decline
        notice, report = record.get("notice"), record.get("verification")
        if notice is None or report is None:
            raise IllegalAction("there is no notice to send")
        if not report["passed"] or report["notice_sha256"] != notice_sha256(Notice(**notice)):
            raise IllegalAction("the notice has not passed verification in its current form")
        record["final"] = {
            "decision": "declined",
            "actor": actor,
            "comment": action.comment,
            "notice_sha256": report["notice_sha256"],
            "at": now(),
        }
        to_status, events = Status.RECORDED, [("declined", actor, {"notice_sha256": report["notice_sha256"]})]

    store.transition(app_id, [Status.NEEDS_REVIEW], row["revision"], to_status, record, events)
    return _load(store, app_id)
