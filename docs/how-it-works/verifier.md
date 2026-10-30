# The notice verifier

`src/credit/guardrails/verifier.py`. Pure Python, no network, no model. It takes the notice and what the notice *must* say (the application, the derived reason codes, the decision being recorded) and returns one pass/fail per check plus a SHA-256 of the exact notice it checked.

| # | Check | Fails when |
|---|---|---|
| V1 | `reasons_match_derivation` | The notice's reason codes differ from the derived ones, in set or order |
| V2 | `reason_count` | A decline has 0 or more than 4 reasons; an approval has any |
| V3 | `no_prohibited_basis` | A reason maps to an excluded attribute, or its text contains a prohibited-basis term (NFKC-normalised, whole words) |
| V4 | `specific_reasons` | A reason does not state the applicant's actual value, or contains a generic phrase ("internal standards", "score too low", …) |
| V5 | `decision_consistent` | The decision statement or field disagrees with the decision being recorded |
| V6 | `numbers_grounded` | The numbers in a reason differ from the numbers in its approved wording filled with the applicant's fields |
| V7 | `legal_frame_intact` | The frame's hash differs from the pinned, reviewed frame |
| V8 | `approved_wording` | A sentence is not exactly an approved variant, contains non-ASCII or control characters, or matches a promise pattern |

Prohibited terms are checked in **reason text only**. The ECOA paragraph is required to name race, sex, age and the other bases, so it is verified by exact hash (V7) instead; a test pins that this is not a false positive.

## Independence

The verifier does not import the renderer. It re-derives the approved sentence from the catalogue with its own substitution and pins the frame by hash. If a developer edits the template, the catalogue, or the code mapping, the verifier and the golden-notice test both fail until the change is reviewed.

## Binding to the exact notice

The report carries `notice_sha256`. The workflow refuses to send a notice whose current hash differs from the verified one, so a stale or tampered notice cannot be sent (tested).

## Mutation suite

`evals/mutations.py` injects one defect at a time into every genuine notice:

| Mutator | Defect | Intended check |
|---|---|---|
| M1 | reorder two reasons | V1 |
| M2 | drop the top reason | V1 |
| M3 | append a fifth, otherwise-approved reason | V1, V2 |
| M4 | "because of your age" appended | V3 |
| M5 | "You did not meet our internal standards." | V4 |
| M6 | decision statement says approved | V5 |
| M7 | reason code not in the catalogue | V1 |
| M8 | a stated number changed | V6 |
| M9 | ECOA statement removed | V7 |
| M10 | "If you reapply with a co-signer we will approve" | V8 |
| M11 | category label swapped for another value | V4 |
| M12 | reason negated | V8 |
| M13 | zero-width character inserted | V8 |
| M14 | unapproved wording variant | V8, V6 |

A mutant is **killed** only when every intended check fails. Mutators that cannot apply (M8 on a notice with no numeric reason) are counted as *not applicable*, never as kills, and every mutator must apply at least once. A mutator that returns an unchanged notice stops the run as a harness bug. The **meta-mutation** switches each check off in turn and requires the gate to fail. Results: [generated results](../evidence/results.md#verifier).

## What it does not do

It does not check that the model is right, that a reason is causal, or that the template is legally adequate. Those are model-validation and legal-review questions.
