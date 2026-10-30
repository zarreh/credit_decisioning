# Regulatory basis

*For orientation only. Checked against the official sources on **2026-10-29**. Not legal advice; any real use would need a compliance review.*

| Source | What this project takes from it | Where |
|---|---|---|
| **ECOA**, 15 U.S.C. 1691 | Prohibited bases (race, color, religion, national origin, sex, marital status, age, public-assistance income, exercise of consumer-protection rights) | Excluded attributes; V3 |
| **Regulation B**, 12 CFR 1002.9(a)(2) | An adverse-action notice states the action taken, the creditor, the ECOA statement, the agency, and the specific reasons | Notice frame |
| **Regulation B**, 12 CFR 1002.9(b)(1) | The ECOA notice text ("substantially similar to…") | `ECOA_STATEMENT`, verified by hash (V7) |
| **Regulation B**, 12 CFR 1002.9(b)(2) | Reasons must be specific and indicate the principal reasons; "internal standards" or "failed to achieve a qualifying score" are insufficient | V4 specificity and generic-phrase list |
| **Regulation B**, 12 CFR 1002.6 and Official Interpretations | Age in empirically derived systems; reasons must relate to factors actually scored | Age excluded (conservative); reasons derived from the scoring model's own coefficients |
| **CFPB Circular 2022-03** | The specific-reasons duty applies equally to complex algorithms; sample-form reasons are not sufficient if they are not the factors actually used. Page live on consumerfinance.gov on 2026-10-29 | Reasons come from the model, not a checklist |
| **FCRA**, 15 U.S.C. 1681m | Additional notice content when a consumer report or credit score is used | Out of scope: no consumer report or score is used, and the notice says so |
| **SR 11-7 / OCC 2011-12** (model risk management) | Conceptual frame: validation, ongoing monitoring, documentation | Evidence pages and gates; no compliance claimed |

Primary sources: [eCFR 12 CFR 1002.9](https://www.ecfr.gov/current/title-12/chapter-X/part-1002/subpart-A/section-1002.9) · [CFPB Circular 2022-03](https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-based-on-complex-algorithms/) · [UCI dataset 144](https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data).

The creditor and agency names in the notice are placeholders. Guidance documents can be withdrawn or superseded; re-check the status of every citation before relying on it.
