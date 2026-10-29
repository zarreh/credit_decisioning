"""The decision policy: the only module that knows the threshold (D-B2-9).

Approving costs 5 if the applicant turns out bad; declining costs 1 if they turn out
good. Declining is the cheaper action when (1 - p) * 1 < p * 5, i.e. p > 1/6. The
threshold is derived from the configured costs, never searched.
"""

from __future__ import annotations

from typing import Final

from credit.schemas import Band

COST_APPROVE_BAD: Final = 5.0
COST_DECLINE_GOOD: Final = 1.0
# Upper edge of the human-review band. A reviewer-capacity policy for the demo, not a
# measured optimum; see docs/decisions/0009-threshold-from-costs.md.
REFER_CEILING: Final = 0.25


def decline_threshold(
    cost_approve_bad: float = COST_APPROVE_BAD, cost_decline_good: float = COST_DECLINE_GOOD
) -> float:
    """Probability of 'bad' above which declining has the lower expected cost."""
    return cost_decline_good / (cost_decline_good + cost_approve_bad)


THRESHOLD: Final = decline_threshold()


def band(p_bad: float) -> Band:
    """Three-way product policy. Exactly at the threshold the two actions tie: refer."""
    if p_bad < THRESHOLD:
        return Band.APPROVE
    if p_bad <= REFER_CEILING:
        return Band.REFER
    return Band.DECLINE


def binary_decline(p_bad: float) -> bool:
    """The evaluated binary policy (used for cost, fairness and baselines)."""
    return p_bad > THRESHOLD
