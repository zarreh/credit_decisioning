# The analyst agent

A read-only assistant beside the product: the only place an LLM is used. It explains the evidence and individual cases, explores the benchmark through aggregates, and drafts reports. It cannot score, decide or change anything, and an import contract forbids `credit.analyst` from importing the workflow, the notice code or the model.

## Built with `create_agent`, tools and middleware

`src/credit/analyst/` is six short files:

| File | Role |
|---|---|
| `agent.py` | One `create_agent(model, tools, middleware, response_format=ToolStrategy(AnalystAnswer), context_schema, checkpointer)` call |
| `tools.py` | Six typed tools over `credit.readmodels` |
| `middleware.py` | The app's four middleware (below) |
| `grounding.py` | Pure-code number check |
| `schemas.py` | `AnalystAnswer {text, claims[{value, source_id, field}]}`, `AnalystContext` |
| `prompt.md` | Versioned system prompt |

**Tools** (each returns JSON with a `source_id`): `get_evidence` (all model-quality evidence in one call), `get_fairness_table` (small groups suppressed), `get_case` (protected attributes removed), `get_queue_summary`, `query_benchmark` (allowlisted count / bad-rate / mean over permitted columns, cells with n < 30 suppressed, protected attributes refused, no raw rows, no SQL), and `save_report_draft`, the only writing tool, which writes a draft row and nothing else.

**Middleware**, in order:

| Purpose | Middleware |
|---|---|
| Refuse decision-changing and protected-attribute requests before any model call | `ScopeGuard` (custom `before_model`, jumps to end) |
| Tell the model which page and case the user is on | `page_context` (`@dynamic_prompt`) |
| After three rounds of tool calls, take the tools away and ask for the answer | `AnswerPush` (custom `wrap_model_call`) |
| Bound spend and loops | `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware` (built-in) |
| Transient model errors | `ModelRetryMiddleware` (built-in) |
| Long conversations | `SummarizationMiddleware` (built-in) |
| A human approves, edits or rejects every report draft before it is saved | `HumanInTheLoopMiddleware(interrupt_on={"save_report_draft": …})` (built-in) |
| Drop a second `save_report_draft` in the same turn (it would raise a second approval prompt) | `OneDraftPerTurn` (custom `after_model`) |
| Log every tool call; turn a refused query into a recoverable message | `ToolAudit` (custom `wrap_tool_call`) |
| Check every number; one repair attempt; then flag | `GroundingMiddleware` (custom `after_model`, can jump back to the model) |

Answers and report drafts are rendered as Markdown in the UI (`react-markdown` with GFM; raw HTML is never rendered and unsafe link schemes become plain text, covered by an end-to-end test). Chat memory uses a SQLite checkpointer per thread; the API streams tool calls, tool results, approval requests and the final answer over SSE.

## Grounding

The answer is structured: text plus a claim per key number citing a `source_id` and a dot path. Code then checks the guarantee that matters: **every number in the text appears in a tool result retrieved in this conversation**, compared at the precision it is displayed ("0.78" and "78%" match 0.779976; "0.781" does not). A whole number must match exactly, so a rounded "21" does not match 21.34, except as a percentage. Numbers inside tool-result strings count too, so a category label such as "0 to 200 DM" can be quoted. Suppressed (null) cells contribute nothing, so their values can never be "found". ISO dates, markdown list numbering, digits inside identifiers (APP-012) and numbers the user wrote are exempt; ranges like "0.49–0.60" count as two numbers.

On failure the problems go back to the model once; if the retry still fails the answer is shown with an amber *unverified* badge listing them.

**Citations are checked but do not decide.** Each claim's `source_id` and `field` are resolved and mismatches are reported as citation notes. A first design made citations the gate; the live model could not produce field paths reliably (it glued paths onto the source id and mis-indexed lists), so almost every correct answer was flagged. The gate was changed to the number-presence rule, which is weaker in one specific way: a number that is real but attributed to the wrong field is not caught, and a small figure can coincide with an unrelated one in the results (a "40%" passes if a label contains "40-61"). A number that appears nowhere in the results is caught.

## Without a key

The analyst is disabled (HTTP 503, and the UI says so); everything else works. Configure `CREDIT_OPENAI_API_KEY` to enable it (see [Run it yourself](../run-it-yourself.md)).

## Evaluation

**Gated, key-free:** `evals/analyst.py` replays a **scripted stand-in** model through the real agent: 19 cases across evidence Q&A, case explanation, data queries, refusals, report approval, rejection and double-save, and grounding attacks (wrong value, wrong source, uncited number, suppressed value, rounded whole number, successful repair). They measure the guard rails, not a live model.

**Not gated, live:** `python -m evals.live_analyst` drives 15 author-written questions through the real API, agent and `gpt-4o-mini`, checking tool use, refusals, approval holds and grounding. Results (generated, with n, model, date and a note that n is too small for an interval): [Results → live run](../evidence/results.md#analyst-live-model-run-not-gated). It found what the stand-in could not, and the fixes it drove are listed in the [case study](../case-study.md#lessons-learned).
