"""Analyst routes: status, chat and resume (both streamed as SSE), and report drafts.

The agent is built once per process. Without an API key the analyst is disabled and
these routes return 503; the rest of the product is unaffected.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from zarreh_agentkit.observability import build_tracing_callbacks, get_logger

from credit.analyst.agent import build_agent, chat_model
from credit.analyst.schemas import AnalystAnswer, AnalystContext
from credit.api.deps import ANALYST_LIMIT, READ_LIMIT, get_store, limiter, settings

router = APIRouter(prefix="/analyst", tags=["analyst"])
log = get_logger("credit.api.analyst")


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message: str = Field(min_length=1, max_length=settings.analyst_max_message_chars)
    page: str = Field(default="analyst", max_length=40)
    case_id: str | None = Field(default=None, max_length=20)


class ResumeRequest(BaseModel):
    thread_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    decision: Literal["approve", "edit", "reject"]
    edited_body: str | None = Field(default=None, max_length=20_000)
    page: str = Field(default="analyst", max_length=40)
    case_id: str | None = Field(default=None, max_length=20)


@lru_cache
def get_agent() -> Any:
    Path(settings.analyst_db_path).parent.mkdir(parents=True, exist_ok=True)
    saver = SqliteSaver(sqlite3.connect(settings.analyst_db_path, check_same_thread=False))
    return build_agent(chat_model(settings), get_store(), settings, saver)


def _require_enabled() -> None:
    if not settings.analyst_enabled:
        raise HTTPException(503, "The analyst is disabled: no model API key is configured (CREDIT_OPENAI_API_KEY).")


def _sse(kind: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": kind, "data": json.dumps(data, default=str)}


def _stream(payload: Any, thread_id: str, context: AnalystContext) -> Iterator[dict[str, str]]:
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": build_tracing_callbacks(settings.langsmith_api_key, settings.langsmith_project),
    }
    answer: AnalystAnswer | None = None
    grounding: dict[str, Any] | None = None
    try:
        for chunk in get_agent().stream(payload, config, context=context, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    yield _sse("approval_needed", {"requests": update[0].value["action_requests"]})
                    return
                if not isinstance(update, dict):
                    continue
                for msg in update.get("messages", []):
                    if isinstance(msg, AIMessage):
                        for call in msg.tool_calls:
                            if call["name"] != "AnalystAnswer":
                                yield _sse("tool_call", {"name": call["name"], "args": call["args"]})
                    elif isinstance(msg, ToolMessage) and msg.name != "AnalystAnswer":
                        source = (
                            json.loads(str(msg.content)).get("source_id") if str(msg.content).startswith("{") else None
                        )
                        yield _sse("tool_result", {"name": msg.name, "source_id": source})
                if isinstance(update.get("structured_response"), AnalystAnswer):
                    answer = update["structured_response"]
                if update.get("grounding"):
                    grounding = update["grounding"]
    except Exception as exc:
        log.exception("analyst.error")
        yield _sse("error", {"detail": f"The analyst failed: {type(exc).__name__}"})
        return
    if answer is None:
        yield _sse(
            "error",
            {"detail": "The analyst stopped without an answer (step limit reached). Try a narrower question."},
        )
        return
    yield _sse(
        "answer",
        {
            **answer.model_dump(),
            "grounding": grounding or {"verified": True, "problems": [], "numbers_checked": 0},
        },
    )


@router.get("/status")
@limiter.limit(READ_LIMIT)
def status(request: Request) -> dict[str, Any]:
    return {
        "enabled": settings.analyst_enabled,
        "model": settings.analyst_model if settings.analyst_enabled else None,
    }


@router.post("/chat")
@limiter.limit(ANALYST_LIMIT)
def chat(request: Request, body: ChatRequest) -> EventSourceResponse:
    _require_enabled()
    context = AnalystContext(page=body.page, case_id=body.case_id)
    return EventSourceResponse(_stream({"messages": [("user", body.message)]}, body.thread_id, context))


@router.post("/resume")
@limiter.limit(ANALYST_LIMIT)
def resume(request: Request, body: ResumeRequest) -> EventSourceResponse:
    _require_enabled()
    decision: dict[str, Any] = {"type": body.decision}
    if body.decision == "edit":
        pending = get_agent().get_state({"configurable": {"thread_id": body.thread_id}}).interrupts
        if not pending or body.edited_body is None:
            raise HTTPException(409, "Nothing to edit: no report is waiting for approval.")
        action = pending[0].value["action_requests"][0]
        decision["edited_action"] = {
            "name": action["name"],
            "args": {**action["args"], "body": body.edited_body},
        }
    if body.decision == "reject":
        decision["message"] = "The reviewer rejected saving this draft."
    context = AnalystContext(page=body.page, case_id=body.case_id)
    return EventSourceResponse(_stream(Command(resume={"decisions": [decision]}), body.thread_id, context))


@router.get("/reports")
@limiter.limit(READ_LIMIT)
def reports(request: Request) -> list[dict[str, Any]]:
    return get_store().drafts()
