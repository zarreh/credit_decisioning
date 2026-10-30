# Case study: a verifier for a regulated artefact

*Problem → verification → gate → lessons learned. Every number below is from the generated [results](evidence/results.md) (run 2026-10-29) and states its n, labels, scorer and uncertainty there.*

## Problem

When a US lender declines credit, ECOA and Regulation B (12 CFR 1002.9) require a written notice with the **specific principal reasons**. "You did not meet our internal standards" or "insufficient score" are explicitly insufficient, and the CFPB's Circular 2022-03 says the duty is the same when the decision comes from a complex model. The notice must also never rest on a prohibited basis such as sex, age or national origin.

Two things go wrong in practice. Reasons drift from what the model actually used (a template edit, a mapping change, a reviewer rewording), and generated text adds things nobody checked: a number, a promise, a protected word. The harm lands on the applicant, who cannot contest a reason they were not told, and on the lender, who carries the regulatory exposure.

The decision itself is cost-asymmetric. In the benchmark's own cost matrix, approving an applicant who turns out bad costs 5 and declining one who would have repaid costs 1. Declining is therefore cheaper whenever the probability of bad exceeds **1/6**, and declining *everyone* (0.70 per applicant) beats approving everyone (1.50). Accuracy against the majority class is the wrong yardstick.

## Verification

What is checked, and by what:

| Artefact | Produced by | Checked by | Ground truth |
|---|---|---|---|
| Probability of bad | Calibrated logistic regression | Repeated 5×5 cross-validation, bootstrap CIs, reliability curve | UCI labels (1994) |
| Band (approve / refer / decline) | Code, from the cost matrix | Unit tests pin `1/(1+5)` and the tie rule | Derived, not tuned |
| Principal reasons | Code, from coefficients vs a frozen training reference | Attributions sum to the logit difference (tested to 1e-9); 8 author-reviewed canonical cases | Model attribution, not cause |
| Notice text | Code, from a reviewed template and catalogue | **Eight deterministic checks** (below); golden text test | Reviewed template (single author) |
| Analyst answers | LLM (`create_agent`) | **Code** grounding: every number must match a tool result | Tool outputs |

The eight notice checks are pure Python; an import-linter contract proves the decision path imports no LLM library. They are: reasons match the derivation (same codes, same order); one to four reasons; no prohibited basis in any reason; each reason specific (states the applicant's actual value, no generic phrases); decision consistent; every number equals the applicant's own field; the legal frame matches a pinned hash; each sentence is an approved wording variant.

**Why a verifier when code already writes the notice?** Because the verifier is an independent second implementation. It does not call the renderer: it pins the legal frame by hash and re-derives the approved wording with its own substitution. It catches template edits, catalogue changes, reviewer variant choices and stale approvals, which is the realistic failure surface. It does not and cannot check that the model is right.

## Gate

`make eval` runs in CI on every pull request and fails the build if any of these break:

- **Model gate:** expected cost below the decline-everyone baseline (0.70) and within bounds pinned from the first real run (≤ 0.56; AUROC ≥ 0.76; ECE ≤ 0.04). Measured: 0.541 [0.488, 0.598], n = 1,000.
- **Verifier gate:** 14 mutators applied to every genuine benchmark notice (1,006, both wordings). Each mutant must fail *its intended check*; a no-op mutation is a harness error, not a kill; inapplicable cases are counted, not hidden. Measured: every applicable mutant killed, 0 genuine notices rejected.
- **Meta-mutation:** each of the eight checks is switched off in turn; the gate must notice every time. Measured: 8 of 8.
- **Analyst gate:** 16 scripted-stand-in cases through the real agent, tools and middleware (grounding, repair, refusals, approval gate). Scorer: scripted stand-in; this measures the guard rails, not a live model.
- **Reproducibility:** `make reproduce` retrains from the pinned data and requires byte-identical evidence (run date aside).

A failure looks like `GATE FAILED: M8 kill rate 0.981` or `disabling numbers_grounded went unnoticed`.

## Honest metrics

- Champion vs boosted challenger: AUROC difference 0.012 [−0.003, 0.029]. The interval includes zero, so the interpretable model's cost is not established on this data.
- ECE's bootstrap interval sits *above* its point estimate. Binned ECE is biased upward under resampling, so that interval is a rough range, not a calibrated CI. Reported anyway, with this caveat.
- Fairness: under-25 applicants are approved at an adverse impact ratio of 0.57, below the 0.8 screen, **although age is not a model input**. The permitted features predict the age band with AUROC 0.73. The 62+ group (n = 38, 7 bad) and non-foreign workers (n = 37, 4 bad) are reported as *insufficient n*, as visible gaps.
- The dataset is 1,000 German applicants from the 1970s to 90s. Nothing here generalises to a current lender.

## Lessons learned

1. **The eval caught a real bug in the grounding guard.** When the analyst's answer failed the number check, the repair feedback (a message quoting the bad numbers) was being read as the user's question, so the bad numbers became *exempt* on the retry. Scripted case G3 failed; the fix tags feedback messages and ignores them. A second test then showed answer numbers were compared against the *claimed* value rather than the *tool's* value, so a claim could launder a wrong number. Both are now pinned by tests.
2. **At a 5:1 cost ratio, "decline everyone" beats "approve everyone".** The useful baseline is 0.70, not 1.50, and the model has to beat it, not a coin flip.
3. **Dropping protected columns does not remove them.** The proxy audit and the under-25 impact ratio make that concrete; the counterfactual-invariance test is documented as a wiring guard, not fairness evidence.
4. **Faithful is not the same as sensible.** In this sample, "critical account / credits at other banks" is associated with *good* outcomes, so "all credits at this bank paid back duly" can appear as a decline reason. The verifier states it faithfully; whether a lender should use such a model is a validation question the verifier cannot answer.
5. **The plan had the cost inequality backwards** (the threshold value was right) and a prohibited-term check that would have rejected the ECOA paragraph itself, which is required to name those bases. Both were corrected before building: prohibited terms are checked in reason text only, and the frame is checked by exact hash.
6. **Moving the LLM out of the notice made the claim stronger.** An earlier design had an LLM paraphrase each reason. Prose cannot be fully verified by code, so the notice became 100% template, and the LLM moved to a read-only analyst where its numbers *can* be checked.
