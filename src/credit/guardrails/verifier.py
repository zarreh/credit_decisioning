"""The adverse-action notice verifier: pure code, no network, no model (D-B2-3).

It is a second, independent implementation of the notice contract. It does not call
the renderer: the legal frame is pinned by hash and reason wording is re-derived from
the catalogue with its own substitution. So it catches template, catalogue, mapping and
reviewer-selection defects, not just malformed input (C16).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from credit.pipeline.attributes import CATEGORY_LABELS, EXCLUDED
from credit.pipeline.reasons import attribute_for, catalogue
from credit.schemas import Application, Check, Notice, VerificationReport

# sha256 of the canonical JSON of the decline frame. Changing the legal frame must be a
# deliberate, reviewed act: update this pin in the same commit (tests/test_verifier.py).
DECLINE_FRAME_SHA256 = "663632fbb5022bc6a157b27ece2e07b3a4bece38f61c80aaa25fd607cee0b3c2"
MAX_REASONS = 4
_NUMBER = re.compile(r"\d[\d,]*")
_SLOT = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class Expected:
    """What the notice must say, computed upstream from the application and model."""

    application: Application
    reason_codes: Sequence[str]
    decision: str


@lru_cache
def _terms() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(Path(__file__).with_name("terms.yaml").read_text())
    return data


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _numbers(text: str) -> Counter[int]:
    return Counter(int(m.replace(",", "")) for m in _NUMBER.findall(text) if m.strip(","))


def _display(application: Application, slot: str) -> str:
    raw = getattr(application, slot)
    return CATEGORY_LABELS[slot][raw] if slot in CATEGORY_LABELS else str(int(raw))


def _approved_text(application: Application, attribute: str, variant: str) -> str | None:
    entry = catalogue()["reasons"].get(attribute)
    template = entry["variants"].get(variant) if entry else None
    if template is None:
        return None
    return _SLOT.sub(lambda m: _display(application, m.group(1)), template)


def frame_sha256(notice: Notice) -> str:
    return hashlib.sha256(notice.frame.model_dump_json().encode()).hexdigest()


def notice_sha256(notice: Notice) -> str:
    payload = json.dumps(notice.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _v1(n: Notice, e: Expected) -> Check:
    got = [r.code for r in n.reasons]
    ok = got == list(e.reason_codes)
    return Check(name="reasons_match_derivation", passed=ok, detail=f"notice {got}, derived {list(e.reason_codes)}")


def _v2(n: Notice, e: Expected) -> Check:
    count = len(n.reasons)
    ok = 1 <= count <= MAX_REASONS if n.decision == "declined" else count == 0
    return Check(name="reason_count", passed=ok, detail=f"{count} reason(s) on a {n.decision} notice")


def _v3(n: Notice, e: Expected) -> Check:
    problems = []
    for r in n.reasons:
        if attribute_for(r.code) in EXCLUDED:
            problems.append(f"{r.code} maps to a prohibited basis")
        text = _norm(r.text)
        problems += [f"{r.code}: '{t}'" for t in _terms()["terms"] if re.search(rf"\b{re.escape(t)}\b", text)]
    return Check(name="no_prohibited_basis", passed=not problems, detail="; ".join(problems) or "none found")


def _v4(n: Notice, e: Expected) -> Check:
    problems = []
    for r in n.reasons:
        attribute = attribute_for(r.code)
        if attribute is None:
            problems.append(f"{r.code} is not in the catalogue")
            continue
        for slot in catalogue()["reasons"][attribute]["slots"]:
            if _display(e.application, slot) not in r.text:
                problems.append(f"{r.code} does not state {slot}")
        text = _norm(r.text)
        problems += [f"{r.code}: generic '{g}'" for g in _terms()["generic_phrases"] if g in text]
    return Check(name="specific_reasons", passed=not problems, detail="; ".join(problems) or "all specific")


def _v5(n: Notice, e: Expected) -> Check:
    stated = _norm(n.frame.decision_statement)
    says = "declined" if "declined" in stated else "approved" if "approved" in stated else "unclear"
    ok = n.decision == e.decision and says == e.decision
    return Check(name="decision_consistent", passed=ok, detail=f"notice {n.decision}/{says}, recorded {e.decision}")


def _v6(n: Notice, e: Expected) -> Check:
    problems = []
    for r in n.reasons:
        attribute = attribute_for(r.code) or ""
        expected = _approved_text(e.application, attribute, r.variant)
        if expected is None:
            problems.append(f"{r.code}: no approved variant '{r.variant}'")
        elif _numbers(r.text) != _numbers(expected):
            problems.append(f"{r.code}: numbers {sorted(_numbers(r.text).elements())} not grounded")
    return Check(name="numbers_grounded", passed=not problems, detail="; ".join(problems) or "all grounded")


def _v7(n: Notice, e: Expected) -> Check:
    digest = frame_sha256(n)
    ok = digest == DECLINE_FRAME_SHA256
    return Check(
        name="legal_frame_intact",
        passed=ok,
        detail="frame matches the pinned text" if ok else f"frame hash {digest[:12]}… differs",
    )


def _v8(n: Notice, e: Expected) -> Check:
    problems = []
    for r in n.reasons:
        if not r.text.isascii() or any(unicodedata.category(c).startswith("C") for c in r.text):
            problems.append(f"{r.code}: non-ASCII or control characters")
        if r.text != _approved_text(e.application, attribute_for(r.code) or "", r.variant):
            problems.append(f"{r.code}: text is not an approved variant")
        problems += [f"{r.code}: promise" for p in _terms()["promise_patterns"] if re.search(p, _norm(r.text))]
    return Check(name="approved_wording", passed=not problems, detail="; ".join(problems) or "all approved")


CHECKS: dict[str, Callable[[Notice, Expected], Check]] = {
    "reasons_match_derivation": _v1,
    "reason_count": _v2,
    "no_prohibited_basis": _v3,
    "specific_reasons": _v4,
    "decision_consistent": _v5,
    "numbers_grounded": _v6,
    "legal_frame_intact": _v7,
    "approved_wording": _v8,
}


def verify(notice: Notice, expected: Expected, *, disabled: Collection[str] = ()) -> VerificationReport:
    """Run V1-V8. ``disabled`` exists only for the meta-mutation test."""
    checks = tuple(fn(notice, expected) for name, fn in CHECKS.items() if name not in disabled)
    return VerificationReport(passed=all(c.passed for c in checks), checks=checks, notice_sha256=notice_sha256(notice))
