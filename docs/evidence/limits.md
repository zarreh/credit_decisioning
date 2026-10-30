# Honest limits

| Limit | Consequence |
|---|---|
| German Credit is 1,000 rows from 1970s–90s Germany, amounts in Deutsche Marks | Not representative of any current lender or population. Intervals are wide |
| About 300 bad outcomes | A single 20% hold-out would hold about 60; we use repeated CV with pooled out-of-fold predictions instead |
| No ground truth for "the correct reason" | Reasons are model attributions relative to the approved training mean. The verifier checks faithfulness to them, not that the model is right or that a reason is causal |
| Some reasons are counter-intuitive | In this sample, a "critical account" history is associated with good outcomes, so "all credits paid back duly" can be a decline reason. Faithful, but a validator would challenge the model |
| No credit-bureau data or score | No consumer report or credit score is used, so the FCRA score-disclosure content is out of scope; the notice says so |
| Attribute 9 mixes sex and marital status; code A95 is absent | Only female/male can be audited |
| 62+ (n = 38) and non-foreign workers (n = 37) are too small | Shown as *insufficient n*, not estimated |
| The 60 queue applicants are synthetic | Resampled and perturbed benchmark rows; no labels and no metrics are computed on them |
| Reason wording, prohibited-term lists and golden fixtures were reviewed by a single author | Not legal review |
| Analyst evaluation uses a scripted stand-in model | It proves the guard rails work, not how good a live model's answers are |
| Live-model analyst run and public hosting not done | Locally runnable and deployment-ready; not deployed |
| Regulation and guidance can change | Citations were checked on 2026-10-29 ([regulatory basis](../regulatory-basis.md)) |

Nothing here is compliance or legal advice. Any real use would need a model-risk validation and a compliance review.
