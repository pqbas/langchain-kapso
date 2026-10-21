import asyncio

import httpx
import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from langchain_kapso import AsyncKapsoClient, InvalidSignatureError, KapsoBridge

from .conftest import PHONE_NUMBER_ID, SECRET, received_payload, webhook_request


def echo_graph(delay: float = 0.0):
    """A graph that answers with the number of human messages it has seen."""

    async def agent(state: MessagesState) -> dict:
        await asyncio.sleep(delay)
        humans = [m for m in state["messages"] if m.type == "human"]
        return {"messages": [AIMessage(f"{humans[-1].content} ({len(humans)})")]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    return builder.compile(checkpointer=InMemorySaver())


def make_bridge(recorder, graph=None) -> KapsoBridge:
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    client = AsyncKapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=http)
    return KapsoBridge(graph or echo_graph(), client, webhook_secret=SECRET)


async def test_replies_on_whatsapp(recorder):
    bridge = make_bridge(recorder)
    body, headers = webhook_request(received_payload("Hola"))

    assert await bridge.handle(body, headers) == ["Hola (1)"]
    read, reply = recorder.bodies()
    assert read["status"] == "read" and read["typing_indicator"] == {"type": "text"}
    assert reply["to"] == "51987654321" and reply["text"] == {"body": "Hola (1)"}


async def test_conversation_keeps_memory(recorder):
    bridge = make_bridge(recorder)
    await bridge.handle(*webhook_request(received_payload("uno", "wamid.1"), key="k1"))
    replies = await bridge.handle(*webhook_request(received_payload("dos", "wamid.2"), key="k2"))
    assert replies == ["dos (2)"]


async def test_retried_delivery_is_processed_once(recorder):
    bridge = make_bridge(recorder)
    request = webhook_request(received_payload("Hola"), key="same-key")
    await bridge.handle(*request)
    assert await bridge.handle(*request) == []


async def test_invalid_signature_is_rejected(recorder):
    bridge = make_bridge(recorder)
    body, headers = webhook_request(received_payload())
    headers["X-Webhook-Signature"] = "forged"
    with pytest.raises(InvalidSignatureError):
        bridge.accept(body, headers)


async def test_same_conversation_runs_in_order(recorder):
    bridge = make_bridge(recorder, echo_graph(delay=0.05))
    first = bridge.accept(*webhook_request(received_payload("uno", "wamid.1"), key="k1"))[0]
    second = bridge.accept(*webhook_request(received_payload("dos", "wamid.2"), key="k2"))[0]

    replies = await asyncio.gather(bridge.process(first), bridge.process(second))
    assert replies == ["uno (1)", "dos (2)"]
