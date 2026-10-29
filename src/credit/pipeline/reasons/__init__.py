"""Principal reasons, derived in code from the champion's coefficients (D-B2-2).

For a logistic model the log-odds is linear in the transformed features, so each
attribute's contribution relative to the frozen reference is exact:
``sum_j coef_j * (x_j - ref_j)`` over the attribute's one-hot / scaled columns. The
contributions sum to ``logit(x) - logit(ref)`` (tested). Reasons are model
attributions relative to the approve-band training mean, not causal claims.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from credit.pipeline.attributes import MODEL_FEATURES
from credit.pipeline.model import CreditModel
from credit.schemas import Reason

MAX_REASONS = 4
CATALOGUE_PATH = Path(__file__).with_name("reasons.yaml")


@lru_cache
def catalogue() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(CATALOGUE_PATH.read_text())
    return data


def code_for(attribute: str) -> str:
    return str(catalogue()["reasons"][attribute]["code"])


def attribute_for(code: str) -> str | None:
    for attribute, entry in catalogue()["reasons"].items():
        if entry["code"] == code:
            return str(attribute)
    return None


def _owner(feature_name: str) -> str:
    # One-hot columns are named "<attribute>_<code>"; scaled numerics keep the name.
    for attribute in MODEL_FEATURES:
        if feature_name == attribute or feature_name.startswith(f"{attribute}_"):
            return attribute
    raise KeyError(feature_name)


def contributions(model: CreditModel, application: pd.DataFrame) -> dict[str, float]:
    """Per-attribute log-odds contribution for a single application row."""
    if len(application) != 1:
        raise ValueError("contributions are computed for exactly one application")
    delta = (model.transformed(application)[0] - model.reference) * model.coefficients()
    totals = dict.fromkeys(MODEL_FEATURES, 0.0)
    for name, value in zip(model.feature_names(), delta, strict=True):
        totals[_owner(name)] += float(value)
    return totals


def principal_reasons(by_attribute: dict[str, float]) -> list[Reason]:
    """Up to four attributes pushing toward 'bad', largest first.

    Ties break by attribute name so the order is deterministic. Contributions of
    exactly zero or below are never reasons; an empty list means a decline cannot be
    explained and must go to manual review, never to a fabricated reason.
    """
    adverse = [(a, c) for a, c in by_attribute.items() if c > 0 and a in catalogue()["reasons"]]
    adverse.sort(key=lambda item: (-round(item[1], 12), item[0]))
    return [Reason(code=code_for(a), attribute=a, contribution=c) for a, c in adverse[:MAX_REASONS]]
