import httpx
import pytest

from langchain_kapso import AsyncKapsoClient, KapsoClient, KapsoError

from .conftest import PHONE_NUMBER_ID


def make_client(recorder) -> KapsoClient:
    http = httpx.Client(transport=httpx.MockTransport(recorder))
    return KapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=http)


def test_send_text_posts_cloud_api_payload(recorder):
    client = make_client(recorder)
    client.send_text("51987654321", "Hola")

    request = recorder.requests[0]
    assert request.url == f"https://api.kapso.ai/meta/whatsapp/v24.0/{PHONE_NUMBER_ID}/messages"
    assert request.headers["X-API-Key"] == "k"
    assert recorder.bodies()[0] == {
        "messaging_product": "whatsapp",
        "to": "51987654321",
        "type": "text",
        "text": {"body": "Hola"},
    }


def test_send_buttons_builds_reply_buttons(recorder):
    make_client(recorder).send_buttons("51987654321", "¿Seguimos?", [{"id": "yes", "title": "Sí"}])
    action = recorder.bodies()[0]["interactive"]["action"]
    assert action["buttons"] == [{"type": "reply", "reply": {"id": "yes", "title": "Sí"}}]


def test_mark_read_with_typing_indicator(recorder):
    make_client(recorder).mark_read("wamid.1", typing_indicator=True)
    assert recorder.bodies()[0] == {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "wamid.1",
        "typing_indicator": {"type": "text"},
    }


def test_list_messages_drops_empty_params(recorder):
    make_client(recorder).list_messages(conversation_id="conv_1", limit=5)
    params = dict(recorder.requests[0].url.params)
    assert params == {"conversation_id": "conv_1", "limit": "5"}


def test_error_response_raises():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "bad key"})))
    client = KapsoClient(api_key="k", phone_number_id="1", http_client=http)
    with pytest.raises(KapsoError) as error:
        client.send_text("1", "x")
    assert error.value.status_code == 401


def test_reads_credentials_from_env(monkeypatch):
    monkeypatch.setenv("KAPSO_API_KEY", "env-key")
    monkeypatch.setenv("KAPSO_PHONE_NUMBER_ID", "999")
    client = KapsoClient()
    assert (client.api_key, client.phone_number_id) == ("env-key", "999")


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("KAPSO_API_KEY", raising=False)
    with pytest.raises(ValueError):
        KapsoClient(phone_number_id="1")


async def test_async_client_sends_text(recorder):
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    client = AsyncKapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=http)
    await client.send_text("51987654321", "Hola")
    assert recorder.bodies()[0]["text"] == {"body": "Hola"}
