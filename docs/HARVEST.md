# Harvest and debt

What B2 reused, what it duplicated, and what should be extracted later.

## Reused

| From | What | How |
|---|---|---|
| `zarreh-agentkit` v0.5.0 | Settings base, structlog setup, LangSmith callbacks, rate limiter, body-size middleware, health router | Pinned git tag, same as A12 |
| A3 `clinical_care_navigator/frontend` | `Callout`, `Card`, `InfoTip`, `Meter`, `PageHeader` primitives, Next.js/Tailwind config, frontend Dockerfile, Playwright config | **Copied** (accent recoloured sky → teal) |
| A3 | Dockerfile and compose shape, CORS policy | Adapted |

## Duplication debt

- **UI primitives (D20 / X3).** No shared `@zarreh/agent-ui` package existed when B2 was built, so the primitives were copied. They now exist in A3, A12 and B2. Extract after the next consumer, per portfolio decision D20.
- **ML evaluation utilities (X4).** `pipeline/evaluate.py` (out-of-fold predictions, bootstrap, paired differences, ECE, reliability) and `pipeline/fairness.py` (small-n-aware group metrics, proxy audit) overlap with A12's pipeline. These are the X4 `zarreh-mlkit` candidates; extract only what both projects use in working code.
- **Mutation-runner pattern.** `evals/run.py`'s applicable/killed/skipped accounting and meta-mutation could serve A2's process audit.

## Readiness review (guide Part A), 2026-10-29

| Area | Status |
|---|---|
| Quality gates | ruff, mypy --strict, import-linter (3 contracts), pytest (114 tests, 95% coverage), eval gate: green |
| Container | Non-root, health check, `.dockerignore` excludes data and secrets, lockfile install |
| Network | No host ports in prod; proxy overwrites `X-Forwarded-For` (documented) |
| Auth | Basic auth at the proxy (documented); no browser keys |
| Unknown id | 404 with guidance, before any work |
| Double start / stale review | Atomic conditional update; 409 (4-thread race test) |
| Background failure | Scoring is synchronous; failures are stored, shown, and retryable |
| Derived state | Queue rebuild is one explicit transaction and clears analyst threads |
| `.env.example` | **Not committed**: blocked by the organisation's content-exclusion policy for this session. Variables are documented in [Deploy](deploy.md#environment) instead |

No open high-severity item.
