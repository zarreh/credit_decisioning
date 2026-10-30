"""Number grounding for the analyst: pure code, no model.

The guarantee is: **every number in the answer appears in a tool result the agent
actually retrieved in this conversation**, compared at the precision it is displayed.
"0.78" matches 0.779976 and "32.58%" matches 0.325806; a whole number must match
exactly (a rounded "21" does not match 21.34), except as a percentage. Numbers inside
tool-result strings count too, so a category label like "0 to 200 DM" can be quoted.
Suppressed (null) cells contribute nothing, so their values can never be "found".

That is deliberately weaker than "each number came from the field the model cites":
a small model cannot reliably produce field paths. Citations are still checked and
reported (``citation_problems``) because they make an answer auditable, but they do not
decide whether it is verified. A number that is real but attributed to the wrong field
is therefore not caught; a number that appears nowhere in the tool results is.
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
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_RANGE_DASH = re.compile(r"(?<=\d)\s*[-\u2013]\s*(?=\d)")
# Markdown list numbering ("1. ", "2) ") at the start of a line is formatting, not a claim.
_LIST_MARKER = re.compile(r"^[ \t]*\d{1,2}[.)][ \t]+", re.MULTILINE)


@dataclass(frozen=True)
class Grounding:
    verified: bool
    problems: list[str] = field(default_factory=list)
    citation_problems: list[str] = field(default_factory=list)
    numbers_checked: int = 0


def _decimals(token: str) -> int:
    parts = token.rstrip("%").split(".")
    return len(parts[1]) if len(parts) > 1 else 0


def _parse(token: str) -> tuple[float, int, bool]:
    return float(token.rstrip("%").replace(",", "")), _decimals(token), token.endswith("%")


def numbers_in(text: str) -> list[str]:
    """Numeric tokens to check. ISO dates and list markers are dropped; '0.49-0.60' counts as
    two numbers; digits inside identifiers (APP-012) are not numbers."""
    cleaned = _RANGE_DASH.sub(" to ", _DATE.sub(" ", _LIST_MARKER.sub("", text)))
    return _NUMBER.findall(cleaned)


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


def facts_in(sources: Mapping[str, Any]) -> list[float]:
    """Every number in the retrieved tool results: numeric leaves and numbers in strings."""
    found: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, int | float):
            found.append(float(node))
        elif isinstance(node, str):
            found.extend(_parse(t)[0] for t in numbers_in(node))
        elif isinstance(node, Mapping):
            for value in node.values():
                walk(value)
        elif isinstance(node, list | tuple):
            for value in node:
                walk(value)

    for source in sources.values():
        walk(source)
    return found


def _present(value: float, decimals: int, percent: bool, facts: Iterable[float]) -> bool:
    tolerance = 0.5 * 10.0**-decimals + 1e-9
    for fact in facts:
        if percent:
            if abs(value - fact) <= tolerance or abs(value - 100 * fact) <= tolerance:
                return True
        elif decimals == 0:
            if abs(value - fact) < 1e-9:
                return True
        elif abs(value - fact) <= tolerance:
            return True
    return False


def _find_source(source_id: str, sources: Mapping[str, Any]) -> tuple[Any, str]:
    """Resolve a cited source. Models often glue the path onto the id
    ("fairness:sex.rows.0.approval_rate"), so fall back to the longest retrieved prefix."""
    if source_id in sources:
        return sources[source_id], ""
    for known in sorted(sources, key=len, reverse=True):
        if source_id.startswith(known + "."):
            return sources[known], source_id[len(known) + 1 :]
    return None, ""


def _check_claim(claim: Claim, sources: Mapping[str, Any]) -> str | None:
    source, glued = _find_source(claim.source_id, sources)
    if source is None:
        return f"{claim.value}: source '{claim.source_id}' was never retrieved"
    path = ".".join(p for p in (glued, claim.field) if p)
    actual = resolve(source, path)
    if not isinstance(actual, int | float) or isinstance(actual, bool):
        return f"{claim.value}: '{path}' in {claim.source_id} is not a number"
    decimals = min(_decimals(repr(claim.value)), 6)
    if not _present(claim.value, decimals, False, [float(actual)]) and not _present(
        claim.value, decimals, True, [float(actual)]
    ):
        return f"{claim.value}: {claim.source_id}.{path} is {actual}"
    return None


def check(text: str, claims: Iterable[Claim], sources: Mapping[str, Any], exempt: Iterable[float] = ()) -> Grounding:
    facts = facts_in(sources)
    allowed = EXEMPT | set(exempt)
    problems = []
    tokens = numbers_in(text)
    for token in tokens:
        value, decimals, percent = _parse(token)
        if value in allowed:
            continue
        if not _present(value, decimals, percent, facts):
            problems.append(f"'{token}' does not appear in any tool result")
    citation_problems = [p for claim in claims if (p := _check_claim(claim, sources))]
    return Grounding(
        verified=not problems, problems=problems, citation_problems=citation_problems, numbers_checked=len(tokens)
    )
