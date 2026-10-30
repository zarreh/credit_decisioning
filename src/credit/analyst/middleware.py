"""The analyst's own middleware. Built-in middleware (limits, retry, HITL,
summarisation) is wired in agent.py; these four cover what is specific to this app.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any, NotRequired

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    dynamic_prompt,
    hook_config,
)
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from zarreh_agentkit.observability import get_logger

from credit.analyst import grounding
from credit.analyst.schemas import AnalystAnswer, AnalystContext
from credit.readmodels import QueryError

log = get_logger("credit.analyst")

FEEDBACK = "grounding_feedback"
REFUSAL = (
    "I can only read and explain. I can't change, approve or decline an application, "
    "predict how a specific person would behave, or infer anyone's sex, age, marital "
    "status or national origin. A human reviewer makes every decision on the Application page."
)
_OUT_OF_BOUNDS = [
    r"\b(approve|decline|deny|reject|override|overturn)\b.*\b(app-\d+|application|case|applicant)\b",
    r"\b(change|set|record|flip)\b.*\b(decision|outcome|recommendation)\b",
    r"\b(guess|infer|predict|estimate|tell me|what is)\b.*"
    r"\b(gender|sex|age|nationality|marital|married|race|religion|foreign)\b.*"
    r"\b(of|for)\b.*\b(app-\d+|applicant|this person|this case)\b",
]


@dynamic_prompt
def page_context(request: ModelRequest) -> str:
    """Base prompt plus where the user is, so 'this case' resolves without asking."""
    ctx = request.runtime.context
    base = str(request.system_prompt or "")
    if isinstance(ctx, AnalystContext) and ctx.case_id:
        return f"{base}\n\nThe user is viewing application {ctx.case_id} on the {ctx.page} page."
    if isinstance(ctx, AnalystContext):
        return f"{base}\n\nThe user is on the {ctx.page} page."
    return base


class ScopeGuard(AgentMiddleware[AgentState[Any], AnalystContext]):
    """Refuse decision-changing or protected-attribute requests before any model call."""

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentState[Any], runtime: Runtime[AnalystContext]) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if not isinstance(last, HumanMessage) or last.name == FEEDBACK:
            return None
        text = str(last.content).lower()
        if any(re.search(p, text) for p in _OUT_OF_BOUNDS):
            answer = AnalystAnswer(text=REFUSAL, claims=[])
            return {"messages": [AIMessage(content=REFUSAL)], "structured_response": answer, "jump_to": "end"}
        return None


class ToolAudit(AgentMiddleware[AgentState[Any], AnalystContext]):
    """Log every tool call (name, arguments, duration) and turn a refused query into a
    message the model can recover from, instead of a crashed run."""

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]]
    ) -> ToolMessage | Command[Any]:
        call = request.tool_call
        started = time.perf_counter()
        try:
            result = handler(request)
        except QueryError as exc:
            log.info("analyst.tool_refused", tool=call["name"], reason=str(exc))
            return ToolMessage(
                content=json.dumps({"error": str(exc)}), tool_call_id=call["id"] or "", name=call["name"]
            )
        log.info(
            "analyst.tool",
            tool=call["name"],
            args=call["args"],
            ms=round(1000 * (time.perf_counter() - started)),
        )
        return result


ANSWER_NOW = (
    "You have already retrieved the data you need. Do not call any more tools: write your final answer "
    "now using only the tool results above, and say plainly if something could not be retrieved."
)


class AnswerPush(AgentMiddleware[AgentState[Any], AnalystContext]):
    """After a few rounds of tool calls, take the tools away and ask for the answer.

    Prompts alone do not stop a small model from re-querying in circles (observed live:
    it never reached its final answer on 7 of 15 questions). A bounded number of rounds
    per turn guarantees it either answers or hits no tools to call."""

    def __init__(self, max_rounds: int = 3) -> None:
        super().__init__()
        self.max_rounds = max_rounds

    @staticmethod
    def rounds(messages: list[Any]) -> int:
        count = 0
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                break
            if isinstance(m, AIMessage) and any(c["name"] != "AnalystAnswer" for c in m.tool_calls):
                count += 1
        return count

    def wrap_model_call(
        self,
        request: ModelRequest[AnalystContext],
        handler: Callable[[ModelRequest[AnalystContext]], ModelResponse[Any]],
    ) -> ModelResponse[Any] | AIMessage:
        if self.rounds(list(request.messages)) >= self.max_rounds:
            request = request.override(tools=[], messages=[*request.messages, HumanMessage(content=ANSWER_NOW)])
        return handler(request)


class OneDraftPerTurn(AgentMiddleware[AgentState[Any], AnalystContext]):
    """A turn may save one report draft. A second save (seen live) would raise a second approval
    prompt for the same request, so the call is dropped and the model is told to answer."""

    @staticmethod
    def saved_this_turn(messages: list[Any]) -> bool:
        for m in reversed(messages):
            if isinstance(m, HumanMessage) and m.name != FEEDBACK:
                return False
            if isinstance(m, ToolMessage) and m.name == "save_report_draft":
                return True
        return False

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: AgentState[Any], runtime: Runtime[AnalystContext]) -> dict[str, Any] | None:
        *earlier, last = state["messages"]
        if not isinstance(last, AIMessage) or not self.saved_this_turn(earlier):
            return None
        kept = [c for c in last.tool_calls if c["name"] != "save_report_draft"]
        if len(kept) == len(last.tool_calls):
            return None
        note = "A report draft was already saved this turn. Do not save another; give your final answer."
        return {
            "messages": [last.model_copy(update={"tool_calls": kept}), HumanMessage(content=note, name=FEEDBACK)],
            "jump_to": "model",
        }


class GroundingState(AgentState[Any]):
    grounding: NotRequired[dict[str, Any]]
    grounding_attempts: NotRequired[int]


def tool_sources(messages: list[Any]) -> dict[str, Any]:
    """Every JSON tool result in the thread, keyed by its source_id."""
    sources: dict[str, Any] = {}
    for m in messages:
        if isinstance(m, ToolMessage):
            try:
                payload = json.loads(str(m.content))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "source_id" in payload:
                sources[payload["source_id"]] = payload
    return sources


def _question(messages: list[Any]) -> str:
    """The user's latest question. Our own repair feedback is a HumanMessage too, and it
    quotes the failing numbers, so it must never count as the question (that would
    exempt exactly the numbers that failed)."""
    users = (m for m in reversed(messages) if isinstance(m, HumanMessage) and m.name != FEEDBACK)
    return next((str(m.content) for m in users), "")


class GroundingMiddleware(AgentMiddleware[GroundingState, AnalystContext]):
    """Check every number in the final answer against the tool results. On failure,
    send the problems back to the model once; then return the answer flagged."""

    state_schema = GroundingState

    def __init__(self, max_repairs: int = 1) -> None:
        super().__init__()
        self.max_repairs = max_repairs

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: GroundingState, runtime: Runtime[AnalystContext]) -> dict[str, Any] | None:
        answer = state.get("structured_response")
        if not isinstance(answer, AnalystAnswer):
            return None
        messages = list(state["messages"])
        exempt = [grounding._parse(t)[0] for t in grounding.numbers_in(_question(messages))]
        result = grounding.check(answer.text, answer.claims, tool_sources(messages), exempt)
        attempts = state.get("grounding_attempts", 0)
        report = {
            "verified": result.verified,
            "problems": result.problems,
            "citation_problems": result.citation_problems,
            "numbers_checked": result.numbers_checked,
            "repairs": attempts,
        }
        if result.verified or attempts >= self.max_repairs:
            return {"grounding": report}
        feedback = "Your answer failed the number check:\n- " + "\n- ".join(result.problems)
        feedback += (
            "\nFix it: every number must be copied from a tool result you retrieved. Do not round whole "
            "numbers, do not compute new figures, and call a tool if you need the number."
        )
        return {
            "messages": [HumanMessage(content=feedback, name=FEEDBACK)],
            "structured_response": None,
            "grounding_attempts": attempts + 1,
            "jump_to": "model",
        }
