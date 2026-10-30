// One plain sentence per term, used by every InfoTip so a term reads the same everywhere.
export const GLOSSARY = {
  adverseAction:
    "A lender's refusal of credit (or worse terms). US law requires telling the applicant the specific principal reasons.",
  reasonCode:
    "One principal reason for a decline, computed by code from the model's coefficients. It names a field on the application.",
  pBad: "The model's calibrated probability that this applicant would not repay (a 'bad' outcome in the benchmark).",
  calibration: "Whether predicted probabilities match observed rates: of applicants scored 30%, about 30% should turn out bad.",
  costMatrix:
    "Approving an applicant who turns out bad costs 5; declining one who would have repaid costs 1. So declining is cheaper above a 1-in-6 chance of bad.",
  band: "Below 1/6 the policy auto-approves; 1/6 to 0.25 goes to a human; above 0.25 the model recommends a decline.",
  verifier:
    "Eight code checks run on every notice before a human can send it. No AI is involved in checking.",
  mutation:
    "A deliberately broken copy of a real notice (e.g. a reason dropped or a number changed). The verifier must reject every one.",
  metaMutation: "Switch one verifier check off and confirm the test suite notices. Proves each check earns its place.",
  adverseImpactRatio:
    "A group's approval rate divided by the highest group's. Below 0.8 is a common screening flag, not a legal finding.",
  proxyAudit:
    "How well the features the model is allowed to use predict an excluded attribute. Above 0.5 means proxies remain.",
  outOfFold: "Every applicant is scored by a model that never saw them, using repeated 5-fold cross-validation.",
  ci95: "95% confidence interval from resampling the 1,000 applicants. Wide intervals mean small samples.",
  grounding: "Code checks that every number in the analyst's answer matches a tool result it actually received.",
  insufficientN: "Fewer than 30 applicants, or fewer than 10 of either outcome: too few to report a number honestly.",
  auroc: "How well the score ranks bad above good applicants: 0.5 is a coin flip, 1.0 is perfect.",
  expectedCost: "Average cost per applicant under the 5-to-1 cost matrix. Lower is better.",
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
