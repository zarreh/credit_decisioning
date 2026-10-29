"""Review-queue routes: list, detail, start scoring, reviewer actions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from credit import workflow
from credit.api.deps import READ_LIMIT, WRITE_LIMIT, get_model, get_store, limiter
from credit.notice import as_text, render_reason
from credit.pipeline.attributes import CATEGORY_LABELS, EXCLUDED, FIELD_NAMES
from credit.pipeline.reasons import attribute_for, catalogue
from credit.schemas import Application, Notice
from credit.store import Conflict

router = APIRouter(prefix="/applications", tags=["applications"])


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    a, r = row["application"], row["record"]
    return {
        "id": row["id"],
        "status": row["status"],
        "revision": row["revision"],
        "purpose": CATEGORY_LABELS["purpose"][a["purpose"]],
        "credit_amount": a["credit_amount"],
        "duration_months": a["duration_months"],
        "p_bad": r.get("score", {}).get("p_bad"),
        "recommendation": r.get("recommendation"),
        "final_decision": (r.get("final") or {}).get("decision"),
        "verification_passed": (r.get("verification") or {}).get("passed"),
        "updated_at": row["updated_at"],
    }


def _detail(row: dict[str, Any]) -> dict[str, Any]:
    application = Application(**row["application"])
    record = row["record"]
    fields = [
        {
            "name": k,
            "label": FIELD_NAMES[k],
            "value": CATEGORY_LABELS[k][v] if k in CATEGORY_LABELS else v,
            "used_by_model": k not in EXCLUDED,
        }
        for k, v in row["application"].items()
    ]
    variant_options = {}
    for reason in record.get("reasons", []):
        attribute = attribute_for(reason["code"]) or ""
        variant_options[reason["code"]] = {
            v: render_reason(application, attribute, v).text for v in catalogue()["reasons"][attribute]["variants"]
        }
    notice = record.get("notice")
    return _summary(row) | {
        "fields": fields,
        "score": record.get("score"),
        "reasons": record.get("reasons", []),
        "notice": notice,
        "notice_text": as_text(Notice(**notice)) if notice else None,
        "verification": record.get("verification"),
        "variant_options": variant_options,
        "final": record.get("final"),
        "error": record.get("error"),
        "events": get_store().events(row["id"]),
    }


def _row(app_id: str) -> dict[str, Any]:
    row = get_store().get(app_id)
    if row is None:
        raise HTTPException(404, f"No application '{app_id}'. Pick one from the queue.")
    return row


@router.get("")
@limiter.limit(READ_LIMIT)
def list_applications(request: Request) -> list[dict[str, Any]]:
    return [_summary(r) for r in get_store().all()]


@router.get("/{app_id}")
@limiter.limit(READ_LIMIT)
def get_application(request: Request, app_id: str) -> dict[str, Any]:
    return _detail(_row(app_id))


@router.post("/{app_id}/start")
@limiter.limit(WRITE_LIMIT)
def start(request: Request, app_id: str) -> dict[str, Any]:
    _row(app_id)
    model = get_model()
    if model is None:
        raise HTTPException(503, "The model artifact is missing. Run `make train` on the server.")
    try:
        return _detail(workflow.start(get_store(), model, app_id))
    except Conflict:
        raise HTTPException(409, "This application has already been started.") from None
    except Exception as exc:
        raise HTTPException(500, f"Scoring failed and the application was marked failed: {exc}") from exc


@router.post("/{app_id}/actions")
@limiter.limit(WRITE_LIMIT)
def act(request: Request, app_id: str, action: workflow.Action) -> dict[str, Any]:
    _row(app_id)
    try:
        return _detail(workflow.act(get_store(), app_id, action))
    except (Conflict, workflow.IllegalAction) as exc:
        detail = (
            str(exc)
            if isinstance(exc, workflow.IllegalAction)
            else "This application changed since you loaded it. Reload and try again."
        )
        raise HTTPException(409, detail) from None
    except workflow.InvalidAction as exc:
        raise HTTPException(422, str(exc)) from None
