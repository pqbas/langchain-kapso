"""Verify and parse Kapso webhook deliveries."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any

MESSAGE_RECEIVED = "whatsapp.message.received"


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Check the ``X-Webhook-Signature`` header, an HMAC SHA256 of the raw body.

    Always pass the bytes exactly as they arrived; a re-serialized JSON body
    produces a different signature.
    """
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@dataclass
class InboundMessage:
    """A customer message received on a WhatsApp number."""

    message_id: str
    conversation_id: str
    phone_number_id: str
    text: str
    type: str
    from_phone: str | None = None
    contact_name: str | None = None
    is_new_conversation: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


def _message_text(message: dict[str, Any]) -> str:
    kapso = message.get("kapso") or {}
    if kapso.get("content"):
        return kapso["content"]
    if message.get("type") == "text":
        return (message.get("text") or {}).get("body", "")
    interactive = message.get("interactive") or {}
    reply = interactive.get("button_reply") or interactive.get("list_reply")
    if reply:
        return reply.get("title", "")
    # Audio messages come with a transcript when Kapso transcription is enabled
    if kapso.get("transcript"):
        return kapso["transcript"]
    return f"[{message.get('type', 'unknown')} message]"


def _to_inbound(item: dict[str, Any]) -> InboundMessage | None:
    message = item.get("message") or {}
    conversation = item.get("conversation") or {}
    if (message.get("kapso") or {}).get("direction", "inbound") != "inbound":
        return None
    return InboundMessage(
        message_id=message.get("id", ""),
        conversation_id=conversation.get("id", ""),
        phone_number_id=item.get("phone_number_id") or conversation.get("phone_number_id", ""),
        text=_message_text(message),
        type=message.get("type", ""),
        from_phone=message.get("from") or conversation.get("phone_number"),
        contact_name=conversation.get("contact_name"),
        is_new_conversation=bool(item.get("is_new_conversation")),
        raw=item,
    )


def parse_inbound_messages(payload: dict[str, Any], event: str | None = None) -> list[InboundMessage]:
    """Return the customer messages in a webhook payload.

    Handles both single deliveries (event name in the ``X-Webhook-Event`` header)
    and buffered batches (``{"batch": true, "type": ..., "data": [...]}``). Any
    event other than ``whatsapp.message.received`` returns an empty list.
    """
    if payload.get("batch"):
        event = payload.get("type", event)
        items = payload.get("data", [])
    else:
        items = [payload]
    if event != MESSAGE_RECEIVED:
        return []
    return [m for m in (_to_inbound(i) for i in items) if m is not None]
