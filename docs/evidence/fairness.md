# Fairness: measure and disclose

The audit's job is to **measure and disclose**, not to certify. It runs on pooled out-of-fold predictions at the binary threshold (decline above 1/6). Numbers: [generated results](results.md#fairness-pooled-out-of-fold-binary-policy).

## Groups

- **Sex:** from UCI attribute 9, which mixes sex and marital status. Code A95 ("female: single") never occurs in the data, so the female group is exactly A92 ("female: divorced, separated or married", n = 310) and cannot be split by marital status. Only female/male is supported.
- **Foreign worker:** UCI attribute 20, used as a crude national-origin proxy. Only 37 applicants are not foreign workers (4 bad), so that group is *insufficient n*.
- **Age band:** under 25, 25–39, 40–61, 62+. The 62+ group (n = 38, 7 bad) is *insufficient n*. Regulation B gives specific protection to applicants 62 and older; this dataset cannot evaluate it, and we say so.

## Metrics per group

Approval rate, adverse impact ratio (group approval rate ÷ highest group's), false-positive rate (good applicants declined), false-negative rate (bad applicants approved), calibration gap (mean predicted − observed bad rate), and expected cost, each with a bootstrap CI. The 0.8 impact-ratio line is a **screening heuristic, not a legal standard**.

**Small-n rule:** fewer than 30 applicants, or fewer than 10 of either outcome, is reported as `insufficient n` with no point estimate. A test pins it.

## Proxy audit

For each excluded attribute, a logistic model on the *permitted* features predicts the attribute (5-fold, binary AUROC or macro one-vs-rest for age bands, with a bootstrap CI). Well above 0.5 means removing the column did not remove its information.

## Finding

Applicants **under 25** are approved at an adverse impact ratio well below the 0.8 screen, although age is not a model input, and the permitted features predict age band with AUROC around 0.73. In a real lender this would need investigation (which features carry age, whether they are justified by business necessity, whether a less discriminatory alternative exists) before any use. This project discloses it; it does not resolve it.

## Counterfactual invariance

A unit test flips sex, age, foreign-worker status and telephone and asserts the score, band and reasons are identical. That is true by construction because those columns are not inputs. The test exists to **catch a future change that wires one back in**. It is not evidence of fairness.
