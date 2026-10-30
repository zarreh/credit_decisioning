# What we measured

All numbers live in the [generated results](results.md), produced by `make train` / `make eval` and written into the docs by `make docs-assets`. Each states the six things the portfolio standard requires: **n**, **label source**, **scorer**, **model version** (or "stand-in"), **run date**, and **uncertainty**.

## Design

- **Data:** UCI Statlog German Credit, 1,000 applicants, 300 bad, SHA-256 pinned. No course copies.
- **Validation:** repeated stratified 5-fold cross-validation, 5 repeats, fixed seed. Every applicant receives five out-of-fold predictions; the per-row mean drives all metrics and the fairness audit. n stays 1,000: repeats are not extra applicants.
- **Leakage control:** preprocessing, calibration (inner 5-fold, `ensemble=False`) and the attribution reference are fitted inside each training split only. Model configurations are fixed up front; nothing is tuned on evaluation data.
- **Uncertainty:** percentile bootstrap over applicants (2,000 resamples) for every metric, and a paired bootstrap for champion-vs-challenger differences. The spread across the five repeats is reported separately as model-fitting noise.
- **Metrics:** AUROC, Brier score, ECE (10 equal-width bins) and expected cost per applicant under the 5:1 cost matrix at the derived threshold. Both trivial policies are reported as baselines.
- **Champion vs challenger:** unweighted L2 logistic regression (serves, exact reasons) vs histogram gradient boosting (offline only). Both sigmoid-calibrated. The challenger measures the price of interpretability; it never replaces the champion silently.
- **Serving model:** refitted on all 1,000 rows *after* evaluation, versioned `champion-lr-sigmoid-v1`. The verifier corpus uses this model on the benchmark rows; that is a verifier test, not a model-performance claim.

## Gates

`evals/gates.yaml` pins bounds from the first real run (2026-10-29) with stated tolerances, and the model must beat the decline-everyone baseline. Changing a bound needs a reviewed commit. See the [case study](../case-study.md#gate).
