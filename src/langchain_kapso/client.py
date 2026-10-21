"""HTTP client for the Kapso WhatsApp API (Meta Cloud API proxy)."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.kapso.ai/meta/whatsapp/v24.0"


class KapsoError(Exception):
    """Raised when the Kapso API returns an error response."""

    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Kapso API error {status_code}: {body}")


def _text_payload(to: str, body: str) -> dict[str, Any]:
    return {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}}


def _buttons_payload(to: str, body: str, buttons: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}} for b in buttons
                ]
            },
        },
    }


def _mark_read_payload(message_id: str, typing_indicator: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    if typing_indicator:
        payload["typing_indicator"] = {"type": "text"}
    return payload


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


class _BaseKapsoClient:
    def __init__(
        self,
        api_key: str | None = None,
        phone_number_id: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.environ.get("KAPSO_API_KEY")
        self.phone_number_id = phone_number_id or os.environ.get("KAPSO_PHONE_NUMBER_ID")
        if not self.api_key:
            raise ValueError("Missing Kapso API key. Pass api_key or set KAPSO_API_KEY.")
        if not self.phone_number_id:
            raise ValueError(
                "Missing phone number id. Pass phone_number_id or set KAPSO_PHONE_NUMBER_ID."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key or "", "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{self.phone_number_id}/{path.lstrip('/')}"

    @staticmethod
    def _handle(response: httpx.Response) -> dict[str, Any]:
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        if response.is_error:
            raise KapsoError(response.status_code, body)
        return body if isinstance(body, dict) else {"data": body}


class KapsoClient(_BaseKapsoClient):
    """Synchronous client for one Kapso WhatsApp phone number.

    Reads ``KAPSO_API_KEY`` and ``KAPSO_PHONE_NUMBER_ID`` from the environment
    when they are not passed explicitly.
    """

    def __init__(self, *args: Any, http_client: httpx.Client | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._http = http_client or httpx.Client(timeout=self.timeout)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._handle(self._http.post(self._url(path), json=payload, headers=self._headers))

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._handle(
            self._http.get(self._url(path), params=_clean(params), headers=self._headers)
        )

    def send_text(self, to: str, body: str) -> dict[str, Any]:
        """Send a text message. Requires an open 24-hour customer service window."""
        return self._post("messages", _text_payload(to, body))

    def send_buttons(self, to: str, body: str, buttons: list[dict[str, str]]) -> dict[str, Any]:
        """Send up to 3 reply buttons, each a dict with ``id`` and ``title``."""
        return self._post("messages", _buttons_payload(to, body, buttons))

    def mark_read(self, message_id: str, typing_indicator: bool = False) -> dict[str, Any]:
        """Mark an inbound message as read, optionally showing a typing indicator."""
        return self._post("messages", _mark_read_payload(message_id, typing_indicator))

    def list_messages(
        self, conversation_id: str | None = None, limit: int = 20, **params: Any
    ) -> dict[str, Any]:
        """List messages, newest first. Filter by ``conversation_id`` for one chat."""
        return self._get("messages", {"conversation_id": conversation_id, "limit": limit, **params})

    def list_conversations(
        self, status: str | None = None, phone_number: str | None = None, limit: int = 20, **params: Any
    ) -> dict[str, Any]:
        """List conversations, optionally filtered by ``status`` or customer ``phone_number``."""
        return self._get(
            "conversations",
            {"status": status, "phone_number": phone_number, "limit": limit, **params},
        )


class AsyncKapsoClient(_BaseKapsoClient):
    """Asynchronous version of :class:`KapsoClient`."""

    def __init__(self, *args: Any, http_client: httpx.AsyncClient | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._http = http_client or httpx.AsyncClient(timeout=self.timeout)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._http.post(self._url(path), json=payload, headers=self._headers)
        return self._handle(response)

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = await self._http.get(self._url(path), params=_clean(params), headers=self._headers)
        return self._handle(response)

    async def send_text(self, to: str, body: str) -> dict[str, Any]:
        return await self._post("messages", _text_payload(to, body))

    async def send_buttons(self, to: str, body: str, buttons: list[dict[str, str]]) -> dict[str, Any]:
        return await self._post("messages", _buttons_payload(to, body, buttons))

    async def mark_read(self, message_id: str, typing_indicator: bool = False) -> dict[str, Any]:
        return await self._post("messages", _mark_read_payload(message_id, typing_indicator))

    async def list_messages(
        self, conversation_id: str | None = None, limit: int = 20, **params: Any
    ) -> dict[str, Any]:
        return await self._get(
            "messages", {"conversation_id": conversation_id, "limit": limit, **params}
        )

    async def list_conversations(
        self, status: str | None = None, phone_number: str | None = None, limit: int = 20, **params: Any
    ) -> dict[str, Any]:
        return await self._get(
            "conversations",
            {"status": status, "phone_number": phone_number, "limit": limit, **params},
        )
