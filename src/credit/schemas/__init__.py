"""Typed records shared by the pipeline, notice, verifier, workflow and API."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Band(StrEnum):
    APPROVE = "approve"
    REFER = "refer"
    DECLINE = "decline"


Variant = Literal["standard", "plain"]


class Application(BaseModel):
    """One credit application, in UCI codes. Protected fields are carried for the
    audit and display only; they are never model inputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checking_status: str
    duration_months: int = Field(ge=1, le=120)
    credit_history: str
    purpose: str
    credit_amount: int = Field(ge=1, le=100_000)
    savings: str
    employment_since: str
    installment_rate: int = Field(ge=1, le=4)
    personal_status_sex: str
    other_debtors: str
    residence_since: int = Field(ge=1, le=4)
    property: str
    age_years: int = Field(ge=18, le=100)
    other_installment_plans: str
    housing: str
    existing_credits: int = Field(ge=1, le=10)
    job: str
    dependents: int = Field(ge=0, le=10)
    telephone: str
    foreign_worker: str


class Reason(BaseModel):
    """One principal reason: an attribute and its signed log-odds contribution."""

    model_config = ConfigDict(frozen=True)

    code: str
    attribute: str
    contribution: float


class Score(BaseModel):
    model_config = ConfigDict(frozen=True)

    p_bad: float
    band: Band
    model_version: str
    contributions: dict[str, float]


class NoticeReason(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    variant: Variant
    text: str


class NoticeFrame(BaseModel):
    """Fixed legal frame filled by code; the verifier compares it verbatim (V7)."""

    model_config = ConfigDict(frozen=True)

    title: str
    creditor: str
    decision_statement: str
    reasons_heading: str
    consumer_report_statement: str
    ecoa_statement: str
    disclaimer: str


class Notice(BaseModel):
    model_config = ConfigDict(frozen=True)

    application_id: str
    decision: Literal["declined", "approved"]
    reasons: tuple[NoticeReason, ...]
    frame: NoticeFrame
    template_version: str
    catalogue_version: str


class Check(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: str


class VerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    checks: tuple[Check, ...]
    notice_sha256: str

    def failed(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed]
