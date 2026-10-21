import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_kapso import AsyncKapsoClient, KapsoBridge, KapsoClient, KapsoHumanHandoffTool, KapsoToolkit

from .conftest import PHONE_NUMBER_ID, SECRET, received_payload, webhook_request

USER_ID = "9f3af238-b283-40e1-bbf7-fcd6a3e79231"


def clients(recorder):
    sync = KapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=httpx.Client(transport=httpx.MockTransport(recorder)))
    aio = AsyncKapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=httpx.AsyncClient(transport=httpx.MockTransport(recorder)))
    return sync, aio


def test_assign_conversation_uses_platform_api(recorder):
    sync, _ = clients(recorder)
    sync.assign_conversation("conv_1", USER_ID, notes="Wants a refund")
    request = recorder.requests[0]
    assert str(request.url) == "https://api.kapso.ai/platform/v1/whatsapp/conversations/conv_1/assignments"
    active = sync.get_active_assignment("conv_1")
    assert active is not None and active["notes"] == "Wants a refund"


def test_unassign_gives_the_conversation_back(recorder):
    sync, _ = clients(recorder)
    sync.assign_conversation("conv_1", USER_ID)
    sync.unassign_conversation("conv_1")
    assert sync.get_active_assignment("conv_1") is None
    assert sync.unassign_conversation("conv_1") is None


def test_handoff_tool_assigns_current_conversation(recorder):
    sync, _ = clients(recorder)
    tool = KapsoHumanHandoffTool(client=sync, handoff_user_id=USER_ID)
    result = tool.invoke({"summary": "Order A100 never arrived"}, config={"configurable": {"kapso_conversation_id": "conv_1"}})
    assert result.startswith("Conversation handed off")
    assert recorder.assignments[0] == {"user_id": USER_ID, "notes": "Order A100 never arrived", "id": "as_1", "active": True}


def test_handoff_tool_needs_the_bridge_config(recorder):
    sync, _ = clients(recorder)
    tool = KapsoHumanHandoffTool(client=sync, handoff_user_id=USER_ID)
    with pytest.raises(ValueError, match="kapso_conversation_id"):
        tool.invoke({"summary": "x"})


def test_toolkit_adds_handoff_only_with_a_user(recorder):
    sync, _ = clients(recorder)
    assert "kapso_human_handoff" not in [t.name for t in KapsoToolkit(client=sync).get_tools()]
    assert "kapso_human_handoff" in [t.name for t in KapsoToolkit(client=sync, handoff_user_id=USER_ID).get_tools()]


class FakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def support_graph(recorder):
    """Agent that hands off on the first message, as a real model would when asked for a person."""
    sync, _ = clients(recorder)
    tools = [KapsoHumanHandoffTool(client=sync, handoff_user_id=USER_ID)]
    model = FakeModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "kapso_human_handoff", "args": {"summary": "Customer asks for a person"}, "id": "t1"}]),
        AIMessage(content="Te paso con una persona del equipo."),
        AIMessage(content="De nuevo conmigo, ¿en qué te ayudo?"),
    ]))

    async def agent(state: MessagesState) -> dict:
        return {"messages": [await model.ainvoke([SystemMessage("support")] + state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=InMemorySaver())


async def test_agent_pauses_while_assigned_and_resumes_after(recorder):
    _, aio = clients(recorder)
    bridge = KapsoBridge(support_graph(recorder), aio, webhook_secret=SECRET)

    # 1. The customer asks for a person: the agent hands off and says so
    assert await bridge.handle(*webhook_request(received_payload("Quiero hablar con una persona", "wamid.1"), key="k1")) == [
        "Te paso con una persona del equipo."
    ]
    assert recorder.assignments[0]["active"]

    # 2. While assigned, the agent stays quiet and does not mark the message as read
    sent_before = len(recorder.bodies())
    assert await bridge.handle(*webhook_request(received_payload("¿Hola?", "wamid.2"), key="k2")) == [None]
    assert len(recorder.bodies()) == sent_before

    # 3. The human unassigns the conversation in Kapso: the agent answers again
    recorder.assignments[0]["active"] = False
    assert await bridge.handle(*webhook_request(received_payload("Gracias", "wamid.3"), key="k3")) == [
        "De nuevo conmigo, ¿en qué te ayudo?"
    ]
