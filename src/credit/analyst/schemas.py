"""Structured output of the analyst, and its runtime context."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """One number the answer states, and where it came from."""

    value: float = Field(description="The number as stated, e.g. 0.78 for '78%' or '0.78'.")
    source_id: str = Field(description="The source_id of the tool result the number comes from.")
    field: str = Field(
        description="Dot path inside that tool result, e.g. 'estimate', 'ci95.0', 'rows.1.approval_rate'."
    )


class AnalystAnswer(BaseModel):
    """The analyst's final answer. Every number in ``text`` must have a claim."""

    text: str = Field(description="The answer in plain English, Markdown allowed.")
    claims: list[Claim] = Field(default_factory=list)


@dataclass(frozen=True)
class AnalystContext:
    """What the user is looking at; injected into the system prompt."""

    page: str = "analyst"
    case_id: str | None = None
