"""Number grounding for the analyst: pure code, no model.

Every number in the answer must (1) be covered by a claim and (2) the claim must
resolve to the same number in a tool result the agent actually received. Numbers are
compared at the precision they are displayed: "0.78" matches 0.779976, and "78%"
matches 0.78 as well as 78. A suppressed (null) value can never ground a claim.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from credit.analyst.schemas import Claim

# Numbers that are labels, not claims: the CI level and the dataset year.
EXEMPT = frozenset({95.0, 1994.0})
_NUMBER = re.compile(r"(?<![\w.-])-?\d[\d,]*(?:\.\d+)?%?(?![\w-])")


@dataclass(frozen=True)
class Grounding:
    verified: bool
    problems: list[str] = field(default_factory=list)
    numbers_checked: int = 0


def _tolerance(token: str) -> float:
    digits = token.rstrip("%").split(".")
    return float(0.5 * 10.0 ** -(len(digits[1]) if len(digits) > 1 else 0) + 1e-9)


def _parse(token: str) -> tuple[float, float, bool]:
    return float(token.rstrip("%").replace(",", "")), _tolerance(token), token.endswith("%")


_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_RANGE_DASH = re.compile(r"(?<=\d)\s*[-\u2013]\s*(?=\d)")


def numbers_in(text: str) -> list[str]:
    """Numeric tokens to check. ISO dates are dropped; '0.49-0.60' counts as two numbers;
    digits inside identifiers (APP-012) are not numbers."""
    return _NUMBER.findall(_RANGE_DASH.sub(" to ", _DATE.sub(" ", text)))


def resolve(source: Any, path: str) -> Any:
    node = source
    for part in path.split(".") if path else []:
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, Mapping) and part in node:
            node = node[part]
        else:
            return None
    return node


def _matches(value: float, tolerance: float, percent: bool, target: float) -> bool:
    if abs(value - target) <= tolerance:
        return True
    return percent and abs(value / 100 - target) <= tolerance / 100


def check(text: str, claims: Iterable[Claim], sources: Mapping[str, Any], exempt: Iterable[float] = ()) -> Grounding:
    problems, grounded = [], []
    for claim in claims:
        actual = resolve(sources.get(claim.source_id), claim.field)
        if claim.source_id not in sources:
            problems.append(f"{claim.value}: source '{claim.source_id}' was never retrieved")
        elif not isinstance(actual, int | float) or isinstance(actual, bool):
            problems.append(f"{claim.value}: '{claim.field}' in {claim.source_id} is not a number")
        elif not _matches(_parse(repr(claim.value))[0], _parse(repr(claim.value))[1], True, float(actual)):
            problems.append(f"{claim.value}: {claim.source_id}.{claim.field} is {actual}")
        else:
            grounded.append(float(actual))
    allowed = EXEMPT | set(exempt)
    tokens = numbers_in(text)
    for token in tokens:
        value, tolerance, percent = _parse(token)
        if value in allowed:
            continue
        if not any(_matches(value, tolerance, percent, g) for g in grounded):
            problems.append(f"'{token}' in the answer has no grounded claim")
    return Grounding(verified=not problems, problems=problems, numbers_checked=len(tokens))
