# The analyst agent

A read-only assistant beside the product: the only place an LLM is used. It explains the evidence and individual cases, explores the benchmark through aggregates, and drafts reports. It cannot score, decide or change anything, and an import contract forbids `credit.analyst` from importing the workflow, the notice code or the model.

## Built with `create_agent`, tools and middleware

`src/credit/analyst/` is six short files:

| File | Role |
|---|---|
| `agent.py` | One `create_agent(model, tools, middleware, response_format=ToolStrategy(AnalystAnswer), context_schema, checkpointer)` call |
| `tools.py` | Seven typed tools over `credit.readmodels` |
| `middleware.py` | The app's four middleware (below) |
| `grounding.py` | Pure-code number check |
| `schemas.py` | `AnalystAnswer {text, claims[{value, source_id, field}]}`, `AnalystContext` |
| `prompt.md` | Versioned system prompt |

**Tools** (each returns JSON with a `source_id`): `get_evidence_metric`, `get_evidence_overview`, `get_fairness_table` (small groups suppressed), `get_case` (protected attributes removed), `get_queue_summary`, `query_benchmark` (allowlisted count / bad-rate / mean over permitted columns, cells with n < 30 suppressed, protected attributes refused, no raw rows, no SQL), and `save_report_draft`, the only writing tool, which writes a draft row and nothing else.

**Middleware**, in order:

| Purpose | Middleware |
|---|---|
| Refuse decision-changing and protected-attribute requests before any model call | `ScopeGuard` (custom `before_model`, jumps to end) |
| Tell the model which page and case the user is on | `page_context` (`@dynamic_prompt`) |
| Bound spend and loops | `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware` (built-in) |
| Transient model errors | `ModelRetryMiddleware` (built-in) |
| Long conversations | `SummarizationMiddleware` (built-in) |
| A human approves, edits or rejects every report draft before it is saved | `HumanInTheLoopMiddleware(interrupt_on={"save_report_draft": …})` (built-in) |
| Log every tool call; turn a refused query into a recoverable message | `ToolAudit` (custom `wrap_tool_call`) |
| Check every number; one repair attempt; then flag | `GroundingMiddleware` (custom `after_model`, can jump back to the model) |

Chat memory uses a SQLite checkpointer per thread; the API streams tool calls, tool results, approval requests and the final answer over SSE.

## Grounding

The answer is structured: text plus one claim per number, citing a `source_id` and a dot path inside that tool result. Code then checks that (1) each claim's source was actually retrieved in the thread, (2) the path resolves to a number, and (3) every number in the text matches a *tool value* at the precision it is displayed ("0.78" and "78%" match 0.779976; "0.781" does not). Suppressed (null) values can never ground a claim. ISO dates, digits inside identifiers (APP-012) and numbers the user wrote are exempt; ranges like "0.49–0.60" count as two numbers. On failure the problems are sent back once; if the retry still fails the answer is shown with an amber *unverified* badge listing them.

## Without a key

The analyst is disabled (HTTP 503, and the UI says so); everything else works. Configure `CREDIT_OPENAI_API_KEY` to enable it (see [Run it yourself](../run-it-yourself.md)).

## Evaluation

`evals/analyst.py` replays a **scripted stand-in** model through the real agent: 16 cases across evidence Q&A, case explanation, data queries, refusals, report approval and rejection, and grounding attacks (wrong value, wrong source, uncited number, suppressed value, successful repair). They gate CI. They measure the guard rails, not a live model's answer quality. A recorded live-model run is an optional follow-up and would be labelled with n, model version, date and cost, and not gated.
