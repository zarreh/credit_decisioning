"""Render an adverse-action notice entirely in code (C5, D-B2-8). No LLM.

The frame is fixed text. The ECOA paragraph follows 12 CFR 1002.9(b)(1) (checked on
eCFR 2026-10-29); the creditor and agency are demonstration placeholders.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from credit.pipeline.attributes import CATEGORY_LABELS
from credit.pipeline.reasons import catalogue
from credit.schemas import Application, Notice, NoticeFrame, NoticeReason, Reason, Variant

TEMPLATE_VERSION = "2026-10-29.1"

ECOA_STATEMENT = (
    "The Federal Equal Credit Opportunity Act prohibits creditors from discriminating "
    "against credit applicants on the basis of race, color, religion, national origin, "
    "sex, marital status, age (provided the applicant has the capacity to enter into a "
    "binding contract); because all or part of the applicant's income derives from any "
    "public assistance program; or because the applicant has in good faith exercised any "
    "right under the Consumer Credit Protection Act. The Federal agency that administers "
    "compliance with this law concerning this creditor is [demonstration placeholder: "
    "the agency name and address would appear here]."
)

DECLINE_FRAME = NoticeFrame(
    title="Notice of action taken on your credit application",
    creditor="[Demonstration creditor: not a real lender]",
    decision_statement="We have declined your application for credit.",
    reasons_heading="Principal reason(s) for our decision:",
    consumer_report_statement=("This decision did not use information from a consumer report or a credit score."),
    ecoa_statement=ECOA_STATEMENT,
    disclaimer=(
        "Portfolio demonstration on the 1994 UCI German Credit benchmark. "
        "Not a real credit decision and not legal advice."
    ),
)


def slot_value(application: Application, slot: str) -> str:
    """The display value of one application field, from the codebook."""
    raw = getattr(application, slot)
    if slot in CATEGORY_LABELS:
        return CATEGORY_LABELS[slot][raw]
    return str(int(raw))


def render_reason(application: Application, attribute: str, variant: Variant) -> NoticeReason:
    entry = catalogue()["reasons"][attribute]
    values = {s: slot_value(application, s) for s in entry["slots"]}
    return NoticeReason(code=entry["code"], variant=variant, text=entry["variants"][variant].format(**values))


def render_decline(
    application_id: str,
    application: Application,
    reasons: Sequence[Reason],
    variants: Mapping[str, Variant] | None = None,
) -> Notice:
    chosen = variants or {}
    return Notice(
        application_id=application_id,
        decision="declined",
        reasons=tuple(render_reason(application, r.attribute, chosen.get(r.code, "standard")) for r in reasons),
        frame=DECLINE_FRAME,
        template_version=TEMPLATE_VERSION,
        catalogue_version=str(catalogue()["version"]),
    )


def as_text(notice: Notice) -> str:
    f = notice.frame
    lines = [f.title, "", f.creditor, "", f.decision_statement, "", f.reasons_heading]
    lines += [f"  {i}. {r.text}" for i, r in enumerate(notice.reasons, start=1)]
    lines += ["", f.consumer_report_statement, "", f.ecoa_statement, "", f.disclaimer]
    return "\n".join(lines)
