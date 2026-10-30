# Decisions (ADRs)

Short records of the choices a reviewer might question. Each: decision, why, and what it costs.

## 0001 No orchestration framework on the decision path

**Decision.** The review workflow is a plain state machine over SQLite with conditional updates; no LangGraph. *Deviates from portfolio plan v4 §9.1 deliberately.*
**Why.** The path is short, fixed and synchronous. A state column plus a revision number gives atomic claims, stale-write protection and an audit log, and keeps the decision path free of LLM and agent libraries (enforced by import-linter).
**Cost.** No graph visualisation of the review flow; progress is a stored event log rather than a streamed graph run.

## 0002 The decision is made in code

**Decision.** The band comes from the calibrated probability and the cost-derived threshold. No model output text can set it.
**Why.** A regulated outcome must not depend on generated wording.

## 0003 Reasons in code; the notice is fully templated

**Decision.** Reasons are derived from the coefficients; the notice is a fixed frame plus reviewed sentences. No LLM writes any notice text. Reviewers choose among approved variants; they never type notice text.
**Why.** Free prose cannot be fully verified by code. Constraining the output lets the verifier make a complete claim.
**Cost.** Less natural wording; adding a wording means a reviewed catalogue change.

## 0004 Protected attributes excluded, then audited; age excluded too

**Decision.** Sex/marital status, age, foreign-worker status and telephone are not model inputs; they are used only for the audit.
**Why.** The conservative reading of Regulation B and the simplest to explain. Proxies are measured, not assumed away.

## 0005 Repeated CV with pooled out-of-fold predictions

**Why.** With 300 bad outcomes a single hold-out would hold about 60. Every applicant gets an honest out-of-fold score.

## 0006 Interpretable champion, boosted challenger

**Decision.** The logistic model serves; gradient boosting is measured offline with a paired CI.
**Why.** Exact reasons need an additive model. The challenger quantifies what that costs (not detectable on this data).

## 0007 Two-layer gate with recorded bounds

**Decision.** Model bounds pinned from the first run plus stated tolerances, plus a must-beat-baseline rule; verifier gated at 100% intended-check kills, zero false rejects and a meta-mutation.
**Why.** The model and the verifier fail in different ways and are gated differently. Bounds are never aspirational.

## 0008 Pinned legal frame

**Decision.** The verifier checks the frame against a pinned SHA-256 rather than importing the template.
**Why.** Verifier independence: a template edit must fail until reviewed.

## 0009 Threshold from the cost matrix

**Decision.** `threshold = c_decline_good / (c_decline_good + c_approve_bad) = 1/6`; ties go to review; refer ceiling 0.25 is a disclosed capacity choice.
**Why.** No threshold search to overfit.

## 0010 Attribution reference

**Decision.** Mean of training applicants the model approves (n = 340 on the serving model). Fallback to good-outcome training rows if fewer than 50 qualify; the provisional check showed about 270 per fold, so the fallback was not needed.
**Why.** "Compared with an applicant we would approve" is the most explainable baseline. Regulation B does not mandate a method.

## 0011 The analyst is `create_agent` with middleware, not Deep Agents

**Decision.** One `create_agent` call with typed read-only tools, built-in middleware (limits, retry, summarisation, human-in-the-loop) and four small custom middleware (scope guard, page context, tool audit, grounding).
**Why.** The jobs are short, tool-grounded Q&A and drafting. Deep Agents' planning, sub-agents and file system would add machinery without benefit.

## 0012 Fixtures are author-reviewed and labelled so

**Decision.** Canonical reason orders and the golden notice were reviewed by a single author on 2026-10-29 and are labelled that way. A model change that moves them must be reviewed, never silently re-pinned.

## 0013 The analyst's numbers are checked against tool values

**Decision.** Structured answers with per-number claims; code checks claims against tool results and the text against tool values at display precision; one repair attempt, then an *unverified* flag.
**Why.** It applies the verifier-engineering idea to generated text where it *can* be applied: numbers.
