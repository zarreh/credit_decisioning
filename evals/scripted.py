"""A scripted stand-in chat model for key-free agent tests and the analyst eval.

It replays a fixed list of AI messages (tool calls, then a structured answer). It
exercises the real agent, tools, middleware and grounding; it measures nothing about a
real model's quality, and every result it produces is labelled "scripted stand-in".
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class ScriptedChatModel(GenericFakeChatModel):
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedChatModel:
        return self


def scripted(*steps: AIMessage) -> ScriptedChatModel:
    return ScriptedChatModel(messages=iter(list(steps)))


_ids = itertools.count(1)


def call(name: str, **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{next(_ids)}"}])


def answer(text: str, *claims: tuple[float, str, str]) -> AIMessage:
    payload = {"text": text, "claims": [{"value": v, "source_id": s, "field": f} for v, s, f in claims]}
    return call("AnalystAnswer", **payload)
