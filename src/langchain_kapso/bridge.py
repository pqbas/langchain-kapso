"""Connect a LangGraph graph to a WhatsApp number through Kapso webhooks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from langchain_kapso.client import AsyncKapsoClient
from langchain_kapso.webhook import InboundMessage, parse_inbound_messages, verify_signature

logger = logging.getLogger(__name__)


class InvalidSignatureError(Exception):
    """The webhook signature is missing or does not match the secret."""


def last_ai_text(state: Mapping[str, Any]) -> str | None:
    """Default reply extractor: the text of the last AI message in ``state["messages"]``."""
    messages: list[BaseMessage] = list(state.get("messages", []))
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return message.text or None
    return None


class KapsoBridge:
    """Runs a LangGraph graph for every customer message and replies on WhatsApp.

    Each Kapso conversation maps to one LangGraph thread (``thread_id`` is the
    conversation id), so a graph compiled with a checkpointer keeps the memory
    of each chat. Messages of the same conversation are processed one at a time
    and in order; different conversations run concurrently.

    ```python
    bridge = KapsoBridge(graph, AsyncKapsoClient())
    app = create_app(bridge)  # from langchain_kapso.server
    ```
    """

    def __init__(
        self,
        graph: Any,
        client: AsyncKapsoClient,
        webhook_secret: str | None = None,
        reply_extractor: Callable[[Mapping[str, Any]], str | None] = last_ai_text,
        typing_indicator: bool = True,
        max_tracked_events: int = 10_000,
    ):
        self.graph = graph
        self.client = client
        self.webhook_secret = webhook_secret or os.environ.get("KAPSO_WEBHOOK_SECRET")
        self.reply_extractor = reply_extractor
        self.typing_indicator = typing_indicator
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._max_tracked = max_tracked_events
        if not self.webhook_secret:
            logger.warning("No webhook secret set; incoming webhooks will not be verified.")

    def accept(self, raw_body: bytes, headers: Mapping[str, str]) -> list[InboundMessage]:
        """Verify and parse a webhook delivery. Call it before answering Kapso.

        Raises :class:`InvalidSignatureError` when the signature is wrong.
        Returns an empty list for other events and for deliveries already seen
        (Kapso retries with the same ``X-Idempotency-Key``).
        """
        headers = {k.lower(): v for k, v in headers.items()}
        if self.webhook_secret and not verify_signature(
            raw_body, headers.get("x-webhook-signature"), self.webhook_secret
        ):
            raise InvalidSignatureError("Invalid Kapso webhook signature")

        key = headers.get("x-idempotency-key")
        if key:
            if key in self._seen:
                return []
            self._seen[key] = None
            if len(self._seen) > self._max_tracked:
                self._seen.popitem(last=False)

        payload = json.loads(raw_body)
        return parse_inbound_messages(payload, headers.get("x-webhook-event"))

    async def process(self, message: InboundMessage) -> str | None:
        """Run the graph for one customer message and send the reply on WhatsApp."""
        async with self._locks[message.conversation_id]:
            try:
                await self.client.mark_read(message.message_id, typing_indicator=self.typing_indicator)
            except Exception:
                logger.exception("Could not mark message %s as read", message.message_id)

            config = {
                "configurable": {
                    "thread_id": message.conversation_id,
                    # Available to nodes and tools through the RunnableConfig
                    "kapso_conversation_id": message.conversation_id,
                    "kapso_phone_number": message.from_phone,
                    "kapso_contact_name": message.contact_name,
                }
            }
            state = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=message.text)]}, config
            )
            reply = self.reply_extractor(state)
            if reply and message.from_phone:
                await self.client.send_text(message.from_phone, reply)
            return reply

    async def handle(self, raw_body: bytes, headers: Mapping[str, str]) -> list[str | None]:
        """Verify, parse and process a delivery in one call (useful in tests and scripts)."""
        messages = self.accept(raw_body, headers)
        return [await self.process(m) for m in messages]
