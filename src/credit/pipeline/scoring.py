"""Score one application: probability, band, contributions and principal reasons.

The single entry point the workflow and the evals use, so the product and the
evidence go through the same code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib

from credit.pipeline.data import to_frame
from credit.pipeline.model import CreditModel
from credit.pipeline.policy import band
from credit.pipeline.reasons import contributions, principal_reasons
from credit.schemas import Application, Reason, Score


@dataclass(frozen=True)
class Scored:
    score: Score
    reasons: list[Reason]


@lru_cache
def load_model(path: str = "artifacts/model.joblib") -> CreditModel:
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} not found: run `make train` first")
    model: CreditModel = joblib.load(path)
    return model


def score(application: Application, model: CreditModel) -> Scored:
    frame = to_frame(application)
    p = float(model.p_bad(frame)[0])
    by_attribute = contributions(model, frame)
    return Scored(
        score=Score(p_bad=p, band=band(p), model_version=model.version, contributions=by_attribute),
        reasons=principal_reasons(by_attribute),
    )
