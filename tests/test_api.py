from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from credit.api import deps
from credit.store import Store


@pytest.fixture
def client(store: Store, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(deps, "get_store", lambda: store)
    from credit.api import analyst, applications, main

    monkeypatch.setattr(applications, "get_store", lambda: store)
    monkeypatch.setattr(analyst, "get_store", lambda: store)
    monkeypatch.setattr(deps.settings, "openai_api_key", "")
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    deps.limiter.reset()
    yield TestClient(main.app)


def test_health(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_queue_and_detail(client: TestClient) -> None:
    rows = client.get("/applications").json()
    assert len(rows) == 60 and rows[0]["status"] == "queued"
    detail = client.get("/applications/APP-001").json()
    used = {f["name"]: f["used_by_model"] for f in detail["fields"]}
    assert used["age_years"] is False and used["duration_months"] is True


def test_unknown_id_is_404_with_guidance(client: TestClient) -> None:
    r = client.post("/applications/APP-999/start")
    assert r.status_code == 404 and "queue" in r.json()["detail"]


def test_start_then_conflict(client: TestClient) -> None:
    assert client.post("/applications/APP-001/start").status_code == 200
    assert client.post("/applications/APP-001/start").status_code == 409


def test_decline_flow_and_status_codes(client: TestClient) -> None:
    decline = next(
        d
        for i in range(1, 61)
        if (d := client.post(f"/applications/APP-{i:03d}/start").json())["recommendation"] == "decline"
    )
    url = f"/applications/{decline['id']}/actions"
    assert decline["verification"]["passed"] and decline["notice_text"]
    assert client.post(url, json={"action": "approve", "expected_revision": decline["revision"]}).status_code == 422
    assert client.post(url, json={"action": "confirm_decline", "expected_revision": 0}).status_code == 409
    done = client.post(url, json={"action": "confirm_decline", "expected_revision": decline["revision"]})
    assert done.status_code == 200 and done.json()["final_decision"] == "declined"
    assert client.post(url, json={"action": "approve", "expected_revision": done.json()["revision"]}).status_code == 409


def test_evidence_routes(client: TestClient) -> None:
    assert client.get("/evidence").json()["provenance"]["n"] == 1000


def test_analyst_disabled_without_key(client: TestClient) -> None:
    assert client.get("/analyst/status").json() == {"enabled": False, "model": None}
    r = client.post("/analyst/chat", json={"thread_id": "abcdefgh", "message": "hi"})
    assert r.status_code == 503 and "CREDIT_OPENAI_API_KEY" in r.json()["detail"]
