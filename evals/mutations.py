"""Mutation suite: proof that the notice verifier catches defective notices (§7.1).

Each mutator injects one defect into a genuine, verified notice. A mutant is killed
only when every one of its intended checks fails. A mutator that does not apply to a
notice (for example, reordering a one-reason notice) is counted as skipped, never as a
kill; a mutator that returns an unchanged notice is a harness error.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from credit.guardrails.verifier import Expected
from credit.pipeline.attributes import CATEGORY_LABELS
from credit.pipeline.reasons import attribute_for, catalogue
from credit.schemas import Notice, NoticeReason

Mutate = Callable[[Notice, Expected], Notice | None]


@dataclass(frozen=True)
class Mutator:
    id: str
    defect: str
    intended: frozenset[str]
    apply: Mutate


def _with_reasons(n: Notice, reasons: list[NoticeReason]) -> Notice:
    return n.model_copy(update={"reasons": tuple(reasons)})


def _edit_text(n: Notice, index: int, text: str) -> Notice:
    reasons = list(n.reasons)
    reasons[index] = reasons[index].model_copy(update={"text": text})
    return _with_reasons(n, reasons)


def _reorder(n: Notice, e: Expected) -> Notice | None:
    if len(n.reasons) < 2:
        return None
    r = list(n.reasons)
    r[0], r[1] = r[1], r[0]
    return _with_reasons(n, r)


def _drop_top(n: Notice, e: Expected) -> Notice | None:
    return _with_reasons(n, list(n.reasons[1:])) if n.reasons else None


def _append_fifth(n: Notice, e: Expected) -> Notice | None:
    if len(n.reasons) != 4:
        return None
    used = {r.code for r in n.reasons}
    attribute, entry = next((a, v) for a, v in catalogue()["reasons"].items() if v["code"] not in used)
    from credit.notice import render_reason  # the real renderer: the fifth reason is "approved"

    return _with_reasons(n, [*n.reasons, render_reason(e.application, attribute, "standard")])


def _prohibited(n: Notice, e: Expected) -> Notice | None:
    return _edit_text(n, 0, n.reasons[0].text.rstrip(".") + ", because of your age.")


def _generic(n: Notice, e: Expected) -> Notice | None:
    return _edit_text(n, 0, "You did not meet our internal standards.")


def _says_approved(n: Notice, e: Expected) -> Notice | None:
    frame = n.frame.model_copy(update={"decision_statement": "We have approved your application for credit."})
    return n.model_copy(update={"frame": frame})


def _unknown_code(n: Notice, e: Expected) -> Notice | None:
    return _with_reasons(n, [n.reasons[0].model_copy(update={"code": "R99"}), *n.reasons[1:]])


def _change_number(n: Notice, e: Expected) -> Notice | None:
    for i, r in enumerate(n.reasons):
        slot = catalogue()["reasons"][attribute_for(r.code) or ""]["slots"][0]
        if slot not in CATEGORY_LABELS:
            value = str(getattr(e.application, slot))
            return _edit_text(n, i, r.text.replace(value, str(int(value) + 7), 1))
    return None


def _drop_ecoa(n: Notice, e: Expected) -> Notice | None:
    return n.model_copy(update={"frame": n.frame.model_copy(update={"ecoa_statement": ""})})


def _promise(n: Notice, e: Expected) -> Notice | None:
    text = n.reasons[0].text + " If you reapply with a co-signer we will approve your application."
    return _edit_text(n, 0, text)


def _swap_category(n: Notice, e: Expected) -> Notice | None:
    for i, r in enumerate(n.reasons):
        slot = catalogue()["reasons"][attribute_for(r.code) or ""]["slots"][0]
        if slot in CATEGORY_LABELS:
            actual = CATEGORY_LABELS[slot][getattr(e.application, slot)]
            other = next(v for v in CATEGORY_LABELS[slot].values() if v != actual and actual not in v)
            return _edit_text(n, i, r.text.replace(actual, other, 1))
    return None


def _negate(n: Notice, e: Expected) -> Notice | None:
    return _edit_text(n, 0, "Not a factor: " + n.reasons[0].text)


def _zero_width(n: Notice, e: Expected) -> Notice | None:
    text = n.reasons[0].text
    return _edit_text(n, 0, text[:3] + "\u200b" + text[3:])


def _unknown_variant(n: Notice, e: Expected) -> Notice | None:
    reasons = list(n.reasons)
    reasons[0] = reasons[0].model_copy(update={"variant": "friendly"})
    return _with_reasons(n, reasons)


MUTATORS: tuple[Mutator, ...] = (
    Mutator("M1", "reorder two reasons", frozenset({"reasons_match_derivation"}), _reorder),
    Mutator("M2", "drop the top reason", frozenset({"reasons_match_derivation"}), _drop_top),
    Mutator("M3", "append a fifth reason", frozenset({"reasons_match_derivation", "reason_count"}), _append_fifth),
    Mutator("M4", "prohibited-basis phrase in a reason", frozenset({"no_prohibited_basis"}), _prohibited),
    Mutator("M5", "generic reason text", frozenset({"specific_reasons"}), _generic),
    Mutator("M6", "decision statement says approved", frozenset({"decision_consistent"}), _says_approved),
    Mutator("M7", "reason code not in the catalogue", frozenset({"reasons_match_derivation"}), _unknown_code),
    Mutator("M8", "a stated number changed", frozenset({"numbers_grounded"}), _change_number),
    Mutator("M9", "ECOA statement removed", frozenset({"legal_frame_intact"}), _drop_ecoa),
    Mutator("M10", "promise of approval added", frozenset({"approved_wording"}), _promise),
    Mutator("M11", "category swapped for another value", frozenset({"specific_reasons"}), _swap_category),
    Mutator("M12", "reason negated", frozenset({"approved_wording"}), _negate),
    Mutator("M13", "zero-width character inserted", frozenset({"approved_wording"}), _zero_width),
    Mutator(
        "M14",
        "unapproved wording variant",
        frozenset({"approved_wording", "numbers_grounded"}),
        _unknown_variant,
    ),
)
