"""LangChain tools that let an agent operate a WhatsApp number through Kapso."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, BaseToolkit
from langchain_core.tools.base import ArgsSchema
from pydantic import BaseModel, ConfigDict, Field

from langchain_kapso.client import AsyncKapsoClient, KapsoClient


def _message_line(message: dict[str, Any]) -> str:
    kapso = message.get("kapso") or {}
    who = "customer" if kapso.get("direction") == "inbound" else "business"
    content = kapso.get("content") or (message.get("text") or {}).get("body") or f"[{message.get('type')}]"
    return f"{who}: {content}"


def format_messages(response: dict[str, Any]) -> str:
    """Turn a ``list_messages`` response into a transcript, oldest message first."""
    messages = list(reversed(response.get("data", [])))
    if not messages:
        return "No messages found."
    return "\n".join(_message_line(m) for m in messages)


def format_conversations(response: dict[str, Any]) -> str:
    conversations = response.get("data", [])
    if not conversations:
        return "No conversations found."
    lines = []
    for c in conversations:
        last = (c.get("kapso") or {}).get("last_message_text") or ""
        lines.append(
            f"id={c.get('id')} phone={c.get('phone_number')} status={c.get('status')} "
            f"last_active_at={c.get('last_active_at')} last_message={last!r}"
        )
    return "\n".join(lines)


class _KapsoTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: KapsoClient
    async_client: AsyncKapsoClient | None = None

    async def _call_async(self, method: str, *args: Any, **kwargs: Any) -> Any:
        # Use the async client when there is one; otherwise run the sync call in a thread
        if self.async_client is not None:
            return await getattr(self.async_client, method)(*args, **kwargs)
        return await asyncio.to_thread(getattr(self.client, method), *args, **kwargs)


class SendTextInput(BaseModel):
    to: str = Field(description="Recipient phone number in international format, digits only, e.g. 51987654321")
    body: str = Field(description="Text of the message")


class KapsoSendTextTool(_KapsoTool):
    name: str = "kapso_send_text"
    description: str = (
        "Send a WhatsApp text message to a phone number. Only works if the customer "
        "wrote to the business in the last 24 hours."
    )
    args_schema: ArgsSchema | None = SendTextInput

    def _run(self, to: str, body: str, **kwargs: Any) -> str:
        response = self.client.send_text(to, body)
        return f"Message sent, id={response.get('messages', [{}])[0].get('id')}"

    async def _arun(self, to: str, body: str, **kwargs: Any) -> str:
        response = await self._call_async("send_text", to, body)
        return f"Message sent, id={response.get('messages', [{}])[0].get('id')}"


class Button(BaseModel):
    id: str = Field(description="Identifier returned when the customer taps the button")
    title: str = Field(description="Button label, max 20 characters")


class SendButtonsInput(BaseModel):
    to: str = Field(description="Recipient phone number in international format, digits only")
    body: str = Field(description="Text shown above the buttons")
    buttons: list[Button] = Field(description="Between 1 and 3 reply buttons", min_length=1, max_length=3)


class KapsoSendButtonsTool(_KapsoTool):
    name: str = "kapso_send_buttons"
    description: str = (
        "Send a WhatsApp message with up to 3 reply buttons, useful to offer the "
        "customer a short list of options."
    )
    args_schema: ArgsSchema | None = SendButtonsInput

    def _run(self, to: str, body: str, buttons: list[Any], **kwargs: Any) -> str:
        response = self.client.send_buttons(to, body, [_as_dict(b) for b in buttons])
        return f"Message sent, id={response.get('messages', [{}])[0].get('id')}"

    async def _arun(self, to: str, body: str, buttons: list[Any], **kwargs: Any) -> str:
        response = await self._call_async("send_buttons", to, body, [_as_dict(b) for b in buttons])
        return f"Message sent, id={response.get('messages', [{}])[0].get('id')}"


def _as_dict(button: Any) -> dict[str, str]:
    return button.model_dump() if isinstance(button, BaseModel) else dict(button)


class GetMessagesInput(BaseModel):
    conversation_id: str = Field(description="Kapso conversation id")
    limit: int = Field(default=20, description="Number of most recent messages to read")


class KapsoGetMessagesTool(_KapsoTool):
    name: str = "kapso_get_messages"
    description: str = "Read the most recent messages of a WhatsApp conversation as a transcript."
    args_schema: ArgsSchema | None = GetMessagesInput

    def _run(self, conversation_id: str, limit: int = 20, **kwargs: Any) -> str:
        return format_messages(self.client.list_messages(conversation_id=conversation_id, limit=limit))

    async def _arun(self, conversation_id: str, limit: int = 20, **kwargs: Any) -> str:
        response = await self._call_async("list_messages", conversation_id=conversation_id, limit=limit)
        return format_messages(response)


class ListConversationsInput(BaseModel):
    status: str | None = Field(default=None, description="'active' or 'ended'")
    phone_number: str | None = Field(default=None, description="Filter by customer phone number")
    limit: int = Field(default=20, description="Maximum number of conversations")


class KapsoListConversationsTool(_KapsoTool):
    name: str = "kapso_list_conversations"
    description: str = "List WhatsApp conversations of the business, with their last message."
    args_schema: ArgsSchema | None = ListConversationsInput

    def _run(self, status: str | None = None, phone_number: str | None = None, limit: int = 20, **kwargs: Any) -> str:
        return format_conversations(
            self.client.list_conversations(status=status, phone_number=phone_number, limit=limit)
        )

    async def _arun(
        self, status: str | None = None, phone_number: str | None = None, limit: int = 20, **kwargs: Any
    ) -> str:
        response = await self._call_async(
            "list_conversations", status=status, phone_number=phone_number, limit=limit
        )
        return format_conversations(response)


class HumanHandoffInput(BaseModel):
    summary: str = Field(
        description="Short summary for the human agent: what the customer needs and what was already checked"
    )


class KapsoHumanHandoffTool(_KapsoTool):
    """Hand the current conversation to a person on the team.

    Assigns the Kapso conversation to ``handoff_user_id`` with the summary as a
    note, so it shows up in the Kapso inbox. While the conversation is assigned,
    :class:`~langchain_kapso.KapsoBridge` stops running the agent for it; when the
    person unassigns it, the agent takes over again with the same memory.

    The conversation id comes from ``config["configurable"]["kapso_conversation_id"]``,
    which the bridge sets on every run.
    """

    name: str = "kapso_human_handoff"
    description: str = (
        "Hand the conversation over to a human agent. Use it when the customer asks "
        "for a person, or when you cannot solve the case with your other tools. "
        "After calling it, tell the customer that a person will continue the chat."
    )
    args_schema: ArgsSchema | None = HumanHandoffInput
    handoff_user_id: str | None = None

    def _target(self, config: RunnableConfig) -> tuple[str, str]:
        conversation_id = (config.get("configurable") or {}).get("kapso_conversation_id")
        user_id = self.handoff_user_id or os.environ.get("KAPSO_HANDOFF_USER_ID")
        if not conversation_id:
            raise ValueError("No kapso_conversation_id in the config; run the graph through KapsoBridge.")
        if not user_id:
            raise ValueError("Missing handoff user. Pass handoff_user_id or set KAPSO_HANDOFF_USER_ID.")
        return conversation_id, user_id

    def _run(self, summary: str, config: RunnableConfig, **kwargs: Any) -> str:
        conversation_id, user_id = self._target(config)
        self.client.assign_conversation(conversation_id, user_id, notes=summary)
        return "Conversation handed off to a human agent. Tell the customer a person will continue shortly."

    async def _arun(self, summary: str, config: RunnableConfig, **kwargs: Any) -> str:
        conversation_id, user_id = self._target(config)
        await self._call_async("assign_conversation", conversation_id, user_id, notes=summary)
        return "Conversation handed off to a human agent. Tell the customer a person will continue shortly."


class KapsoToolkit(BaseToolkit):
    """All Kapso tools, ready to pass to ``model.bind_tools`` or a ``ToolNode``.

    ```python
    toolkit = KapsoToolkit(client=KapsoClient())
    tools = toolkit.get_tools()
    ```
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: KapsoClient
    async_client: AsyncKapsoClient | None = None
    handoff_user_id: str | None = None
    """Team member who receives handed-off conversations. Adds ``kapso_human_handoff`` when set."""

    def get_tools(self) -> list[BaseTool]:
        kwargs = {"client": self.client, "async_client": self.async_client}
        tools: list[BaseTool] = [
            KapsoSendTextTool(**kwargs),
            KapsoSendButtonsTool(**kwargs),
            KapsoGetMessagesTool(**kwargs),
            KapsoListConversationsTool(**kwargs),
        ]
        if self.handoff_user_id:
            tools.append(KapsoHumanHandoffTool(**kwargs, handoff_user_id=self.handoff_user_id))
        return tools
