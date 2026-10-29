from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from credit.guardrails.verifier import DECLINE_FRAME_SHA256, Expected, verify
from credit.notice import DECLINE_FRAME, ECOA_STATEMENT, as_text, render_decline
from credit.pipeline.model import CreditModel
from credit.pipeline.scoring import score
from credit.schemas import Notice
from evals.mutations import MUTATORS
from tests.conftest import application_of

# Author-reviewed golden notice (single author, 2026-10-29). If the renderer, template
# or catalogue changes this text, the change must be reviewed and this file updated.
GOLDEN_UCI_0001 = """\
Notice of action taken on your credit application

[Demonstration creditor: not a real lender]

We have declined your application for credit.

Principal reason(s) for our decision:
  1. Status of existing checking account: 0 to 200 DM.
  2. Length of the requested loan term: 48 months.
  3. Savings account or bonds balance: below 100 DM.
  4. Credit history: existing credits paid back duly so far.

This decision did not use information from a consumer report or a credit score.
"""


@pytest.fixture
def genuine(benchmark: pd.DataFrame, model: CreditModel) -> tuple[Notice, Expected]:
    application = application_of(benchmark, "uci-0001")
    scored = score(application, model)
    notice = render_decline("uci-0001", application, scored.reasons)
    return notice, Expected(application, [r.code for r in scored.reasons], "declined")


def test_golden_notice_text(genuine: tuple[Notice, Expected]) -> None:
    assert as_text(genuine[0]).startswith(GOLDEN_UCI_0001)


def test_frame_pin_matches_template() -> None:
    assert hashlib.sha256(DECLINE_FRAME.model_dump_json().encode()).hexdigest() == DECLINE_FRAME_SHA256


def test_ecoa_statement_follows_regulation_b() -> None:
    # 12 CFR 1002.9(b)(1), checked on eCFR 2026-10-29.
    assert "on the basis of race, color, religion, national origin, sex, marital status, age" in ECOA_STATEMENT
    assert "Consumer Credit Protection Act" in ECOA_STATEMENT


def test_genuine_notice_passes_every_check(genuine: tuple[Notice, Expected]) -> None:
    report = verify(*genuine)
    assert report.passed, report.failed()
    assert len(report.checks) == 8


def test_protected_words_in_ecoa_frame_are_not_false_positives(genuine: tuple[Notice, Expected]) -> None:
    notice, expected = genuine
    assert "sex" in notice.frame.ecoa_statement
    assert verify(notice, expected).passed


def test_plain_variants_also_pass(benchmark: pd.DataFrame, model: CreditModel) -> None:
    application = application_of(benchmark, "uci-0001")
    scored = score(application, model)
    notice = render_decline("x", application, scored.reasons, {r.code: "plain" for r in scored.reasons})
    assert verify(notice, Expected(application, [r.code for r in scored.reasons], "declined")).passed


@pytest.mark.parametrize("mutator", MUTATORS, ids=lambda m: m.id)
def test_each_mutator_is_killed_by_its_intended_check(mutator, genuine: tuple[Notice, Expected]) -> None:  # type: ignore[no-untyped-def]
    notice, expected = genuine
    mutant = mutator.apply(notice, expected)
    assert mutant is not None and mutant != notice
    assert mutator.intended <= set(verify(mutant, expected).failed())


def test_disabled_check_lets_its_mutant_through(genuine: tuple[Notice, Expected]) -> None:
    notice, expected = genuine
    m9 = next(m for m in MUTATORS if m.id == "M9")
    mutant = m9.apply(notice, expected)
    assert mutant is not None
    assert verify(mutant, expected, disabled={"legal_frame_intact"}).passed


def test_report_is_bound_to_the_exact_notice(genuine: tuple[Notice, Expected]) -> None:
    notice, expected = genuine
    edited = notice.model_copy(update={"application_id": "other"})
    assert verify(notice, expected).notice_sha256 != verify(edited, expected).notice_sha256
