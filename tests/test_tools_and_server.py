import httpx
from fastapi.testclient import TestClient

from langchain_kapso import AsyncKapsoClient, KapsoBridge, KapsoClient, KapsoToolkit
from langchain_kapso.server import create_app

from .conftest import PHONE_NUMBER_ID, SECRET, received_payload, webhook_request
from .test_bridge import echo_graph


def make_tools(recorder):
    http = httpx.Client(transport=httpx.MockTransport(recorder))
    client = KapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=http)
    return {t.name: t for t in KapsoToolkit(client=client).get_tools()}


def test_toolkit_tool_names(recorder):
    assert sorted(make_tools(recorder)) == [
        "kapso_get_messages",
        "kapso_list_conversations",
        "kapso_send_buttons",
        "kapso_send_text",
    ]


def test_send_text_tool(recorder):
    result = make_tools(recorder)["kapso_send_text"].invoke({"to": "51987654321", "body": "Hola"})
    assert result.startswith("Message sent")
    assert recorder.bodies()[0]["text"] == {"body": "Hola"}


def test_send_buttons_tool_accepts_dicts(recorder):
    tool = make_tools(recorder)["kapso_send_buttons"]
    tool.invoke({"to": "1", "body": "¿Seguimos?", "buttons": [{"id": "yes", "title": "Sí"}]})
    assert recorder.bodies()[0]["interactive"]["action"]["buttons"][0]["reply"]["title"] == "Sí"


def test_get_messages_tool_returns_transcript_oldest_first(recorder):
    result = make_tools(recorder)["kapso_get_messages"].invoke({"conversation_id": "conv_1"})
    assert result == "customer: Hola\nbusiness: ¿En qué te ayudo?"


async def test_tool_async_falls_back_to_sync_client(recorder):
    result = await make_tools(recorder)["kapso_list_conversations"].ainvoke({"status": "active"})
    assert "id=conv_1" in result


def test_server_answers_and_runs_agent(recorder):
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    client = AsyncKapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=http)
    app = create_app(KapsoBridge(echo_graph(), client, webhook_secret=SECRET))

    with TestClient(app) as test_client:
        body, headers = webhook_request(received_payload("Hola"))
        assert test_client.post("/webhooks/whatsapp", content=body, headers=headers).status_code == 200
        headers["X-Webhook-Signature"] = "forged"
        headers["X-Idempotency-Key"] = "other"
        assert test_client.post("/webhooks/whatsapp", content=body, headers=headers).status_code == 401

    # The background task ran the graph and sent the reply
    assert recorder.bodies()[-1]["text"] == {"body": "Hola (1)"}
