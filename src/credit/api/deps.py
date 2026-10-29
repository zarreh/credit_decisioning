"""Shared API dependencies: settings, store, model, rate limiter."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from zarreh_agentkit.api.rate_limit import build_limiter

from credit.pipeline.model import CreditModel
from credit.pipeline.scoring import load_model
from credit.settings import get_settings
from credit.store import Store

limiter = build_limiter()
settings = get_settings()
WRITE_LIMIT = f"{settings.write_rate_limit_per_minute}/minute"
READ_LIMIT = f"{settings.read_rate_limit_per_minute}/minute"
ANALYST_LIMIT = f"{settings.analyst_rate_limit_per_minute}/minute"


@lru_cache
def get_store() -> Store:
    store = Store(settings.db_path)
    if not store.all() and Path(settings.queue_path).exists():
        # First run only: an empty database is seeded. Resetting a used database is an
        # explicit, destructive command (`make queue-reset`), never a startup side effect.
        items = json.loads(Path(settings.queue_path).read_text())
        store.rebuild([(i["id"], i["application"]) for i in items])
    return store


def get_model() -> CreditModel | None:
    try:
        return load_model(settings.model_path)
    except FileNotFoundError:
        return None
