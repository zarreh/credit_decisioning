# Credit Decisioning

**When credit is declined, the applicant must be told the specific reasons. This project makes those reasons checkable.**

![The application page: model attributions, the eight verifier checks, the drafted notice and the reviewer's decision](assets/screenshots/light/04-application-decline-review.png#only-light)
![The application page](assets/screenshots/dark/04-application-decline-review.png#only-dark)

A calibrated logistic regression scores a consumer-credit application. **Code, not AI**, applies a cost-derived policy, derives up to four principal reasons from the model's coefficients, and writes the adverse-action notice from a reviewed template. A **separate code verifier** checks every notice with eight rules, and a mutation suite proves those rules catch 14 kinds of defect. **A human decides.** Beside the product, a **read-only AI analyst** answers questions and drafts reports; code checks every number it states.

| Owner | Step |
|---|---|
| Model | Calibrated probability that the applicant would not repay |
| Code | Cost policy (decline is cheaper above p = 1/6), principal reasons, notice text, eight verifier checks |
| Human | Approve, send the verified notice, or override with a comment |
| AI (read-only) | Explain the evidence and cases, explore aggregates, draft reports (saved only with approval) |

!!! warning "A method demonstration, not a lender"
    Built on the 1994 UCI German Credit benchmark (1,000 applicants, amounts in Deutsche Marks). The review queue holds 60 synthetic applicants derived from it. Not compliance or legal advice. See [Honest limits](evidence/limits.md).

**Start with the [case study](case-study.md)**, or [run it yourself](run-it-yourself.md) in two commands.
