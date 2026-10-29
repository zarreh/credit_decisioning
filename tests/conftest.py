from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from credit.pipeline.data import load, to_application
from credit.pipeline.model import CreditModel
from credit.pipeline.scoring import load_model
from credit.schemas import Application
from credit.store import Store

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def benchmark() -> pd.DataFrame:
    return load(ROOT / "data/raw")


@pytest.fixture(scope="session")
def model() -> CreditModel:
    return load_model(str(ROOT / "artifacts/model.joblib"))


@pytest.fixture(scope="session")
def queue() -> list[dict[str, object]]:
    data: list[dict[str, object]] = json.loads((ROOT / "data/queue.json").read_text())
    return data


@pytest.fixture
def store(tmp_path: Path, queue: list[dict[str, object]]) -> Iterator[Store]:
    s = Store(str(tmp_path / "test.db"))
    s.rebuild([(str(i["id"]), i["application"]) for i in queue])  # type: ignore[misc]
    yield s


def application_of(benchmark: pd.DataFrame, row_id: str) -> Application:
    return to_application(benchmark[benchmark["row_id"] == row_id].iloc[0])
