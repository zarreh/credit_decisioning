from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from credit.analyst.agent import build_agent
from credit.api import analyst, deps
from credit.store import Store
from evals.scripted import answer, call, scripted

AUROC = "evidence"


@pytest.fixture
def use_script(store: Store, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., TestClient]]:
    from credit.api import main

    monkeypatch.setattr(deps.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(analyst, "get_store", lambda: store)
    deps.limiter.reset()

    def install(*steps: AIMessage) -> TestClient:
        agent = build_agent(scripted(*steps), store, deps.settings, InMemorySaver())
        monkeypatch.setattr(analyst, "get_agent", lambda: agent)
        return TestClient(main.app)

    yield install


def events(response: Any) -> list[tuple[str, dict[str, Any]]]:
    out, kind = [], ""
    for line in response.text.splitlines():
        if line.startswith("event:"):
            kind = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            out.append((kind, json.loads(line.split(":", 1)[1])))
    return out


def chat(client: TestClient, message: str, **extra: Any) -> list[tuple[str, dict[str, Any]]]:
    body = {"thread_id": "thread-1", "message": message} | extra
    return events(client.post("/analyst/chat", json=body))


def test_chat_streams_tools_then_a_verified_answer(use_script: Callable[..., TestClient]) -> None:
    client = use_script(call("get_evidence"), answer("AUROC is 0.78.", (0.78, AUROC, "champion.auroc.estimate")))
    stream = chat(client, "How good is it?", page="evidence")
    assert [k for k, _ in stream] == ["tool_call", "tool_result", "answer"]
    assert stream[1][1]["source_id"] == AUROC
    assert stream[-1][1]["grounding"]["verified"] is True


def test_unverified_answer_is_flagged(use_script: Callable[..., TestClient]) -> None:
    client = use_script(
        call("get_evidence"),
        answer("AUROC is 0.91.", (0.91, AUROC, "champion.auroc.estimate")),
        answer("AUROC is 0.91.", (0.91, AUROC, "champion.auroc.estimate")),
    )
    final = chat(client, "auroc?", case_id="APP-001")[-1][1]
    assert final["grounding"]["verified"] is False and final["grounding"]["problems"]


def test_report_needs_approval_and_edit_is_saved(use_script: Callable[..., TestClient], store: Store) -> None:
    client = use_script(call("save_report_draft", kind="queue", title="Q", body="v1"), answer("Saved."))
    paused = chat(client, "draft a queue report")
    assert paused[-1][0] == "approval_needed" and not store.drafts()
    body = {"thread_id": "thread-1", "decision": "edit", "edited_body": "v2 edited"}
    resumed = events(client.post("/analyst/resume", json=body))
    assert resumed[-1][0] == "answer"
    assert store.drafts()[0]["body"] == "v2 edited"


def test_reject_saves_nothing(use_script: Callable[..., TestClient], store: Store) -> None:
    client = use_script(call("save_report_draft", kind="queue", title="Q", body="v1"), answer("Not saved."))
    chat(client, "draft a queue report")
    events(client.post("/analyst/resume", json={"thread_id": "thread-1", "decision": "reject"}))
    assert store.drafts() == []
    assert client.get("/analyst/reports").json() == []


def test_edit_without_pending_request_conflicts(use_script: Callable[..., TestClient]) -> None:
    client = use_script()
    body = {"thread_id": "thread-9", "decision": "edit", "edited_body": "x"}
    assert client.post("/analyst/resume", json=body).status_code == 409


def test_no_answer_becomes_an_error_event(use_script: Callable[..., TestClient]) -> None:
    client = use_script(AIMessage(content="I am not using the answer tool"))
    assert chat(client, "hello")[-1][0] == "error"


def test_exceptions_become_error_events(use_script: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch) -> None:
    client = use_script()

    class Broken:
        def stream(self, *_: Any, **__: Any) -> Any:
            raise RuntimeError("boom")

    monkeypatch.setattr(analyst, "get_agent", lambda: Broken())
    assert chat(client, "hello")[-1] == ("error", {"detail": "The analyst failed: RuntimeError"})


def test_invalid_thread_id_is_rejected(use_script: Callable[..., TestClient]) -> None:
    client = use_script()
    assert client.post("/analyst/chat", json={"thread_id": "../x", "message": "hi"}).status_code == 422
