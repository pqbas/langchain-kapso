import hashlib
import hmac
import json

import httpx
import pytest

PHONE_NUMBER_ID = "123456789012345"
SECRET = "test-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def received_payload(text: str = "Hola", message_id: str = "wamid.1", conversation_id: str = "conv_1") -> dict:
    """A whatsapp.message.received payload, as in the Kapso docs."""
    return {
        "message": {
            "id": message_id,
            "timestamp": "1730092800",
            "type": "text",
            "from": "51987654321",
            "text": {"body": text},
            "kapso": {"direction": "inbound", "status": "received", "content": text},
        },
        "conversation": {
            "id": conversation_id,
            "contact_name": "Ana",
            "phone_number": "51987654321",
            "phone_number_id": PHONE_NUMBER_ID,
        },
        "is_new_conversation": True,
        "phone_number_id": PHONE_NUMBER_ID,
    }


def webhook_request(payload: dict, event: str = "whatsapp.message.received", key: str = "key-1"):
    body = json.dumps(payload).encode()
    headers = {
        "X-Webhook-Signature": sign(body),
        "X-Webhook-Event": event,
        "X-Idempotency-Key": key,
        "Content-Type": "application/json",
    }
    return body, headers


class Recorder:
    """httpx transport that records requests and answers like the Kapso API."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.assignments: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/assignments"):
            if request.method == "POST":
                assignment = {**json.loads(request.content)["assignment"], "id": "as_1", "active": True}
                self.assignments.insert(0, assignment)
                return httpx.Response(201, json={"data": assignment})
            return httpx.Response(200, json={"data": self.assignments})
        if "/assignments/" in request.url.path and request.method == "PATCH":
            assignment = next(a for a in self.assignments if request.url.path.endswith(a["id"]))
            assignment.update(json.loads(request.content)["assignment"])
            return httpx.Response(200, json={"data": assignment})
        if request.method == "POST":
            return httpx.Response(200, json={"messages": [{"id": f"wamid.out{len(self.requests)}"}]})
        if request.url.path.endswith("/messages"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "m2", "type": "text", "kapso": {"direction": "outbound", "content": "¿En qué te ayudo?"}},
                        {"id": "m1", "type": "text", "kapso": {"direction": "inbound", "content": "Hola"}},
                    ]
                },
            )
        return httpx.Response(
            200,
            json={"data": [{"id": "conv_1", "phone_number": "51987654321", "status": "active", "kapso": {"last_message_text": "Hola"}}]},
        )

    def bodies(self) -> list[dict]:
        """Bodies sent to the WhatsApp messages endpoint."""
        return [
            json.loads(r.content)
            for r in self.requests
            if r.method == "POST" and r.url.path.endswith("/messages")
        ]


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()
