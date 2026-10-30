"""Build the Credit Analyst: one ``create_agent`` call, tools plus middleware.

Built-in middleware does the generic work (call limits, retry, human approval for the
one writing tool, summarising long chats); the app's own middleware adds page context,
the scope guard, tool auditing and number grounding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from credit.analyst.middleware import (
    AnswerPush,
    GroundingMiddleware,
    OneDraftPerTurn,
    ScopeGuard,
    ToolAudit,
    page_context,
)
from credit.analyst.schemas import AnalystAnswer, AnalystContext
from credit.analyst.tools import build_tools
from credit.settings import Settings
from credit.store import Store

SYSTEM_PROMPT = Path(__file__).with_name("prompt.md").read_text()


def chat_model(settings: Settings) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=settings.analyst_model, api_key=settings.openai_api_key, temperature=0)  # type: ignore[arg-type]


def build_agent(
    model: BaseChatModel, store: Store, settings: Settings, checkpointer: BaseCheckpointSaver[Any] | None
) -> Any:
    middleware: list[AgentMiddleware[Any, Any]] = [
        ScopeGuard(),
        page_context,
        AnswerPush(max_rounds=settings.analyst_max_tool_rounds),
        ModelCallLimitMiddleware(run_limit=settings.analyst_max_model_calls, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=settings.analyst_max_tool_calls),
        ModelRetryMiddleware(max_retries=2),
        SummarizationMiddleware(model, trigger=("tokens", 8000), keep=("messages", 12)),
        HumanInTheLoopMiddleware(
            interrupt_on={"save_report_draft": {"allowed_decisions": ["approve", "edit", "reject"]}}
        ),
        OneDraftPerTurn(),  # after HITL: after_model hooks run in reverse, so it acts before an approval prompt
        ToolAudit(),
        GroundingMiddleware(max_repairs=1),
    ]
    return create_agent(
        model,
        tools=build_tools(store, settings.evidence_path),
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(AnalystAnswer),
        context_schema=AnalystContext,
        checkpointer=checkpointer,
        middleware=middleware,
    )
