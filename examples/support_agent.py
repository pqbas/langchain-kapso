"""A WhatsApp support agent for an online store, built with LangGraph and Kapso.

Run it:
    uv run --extra server uvicorn examples.support_agent:app --port 8000

Then expose the port (for example with `cloudflared tunnel --url http://localhost:8000`)
and add a webhook in Kapso for `whatsapp.message.received` pointing to
https://<your-tunnel>/webhooks/whatsapp.
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_kapso import AsyncKapsoClient, KapsoBridge, KapsoClient, KapsoHumanHandoffTool
from langchain_kapso.server import create_app

load_dotenv()

model = init_chat_model("anthropic:claude-haiku-5-5")

SYSTEM_PROMPT = (
    "You are the support agent of an online store, chatting on WhatsApp. "
    "Answer briefly and kindly, in the customer's language. "
    "Use the tools to look up data, never make it up. "
    "If the customer asks for a person or you cannot help, hand the conversation off."
)

ORDERS = {
    "A100": {"status": "shipped", "item": "Headphones"},
    "A101": {"status": "delivered", "item": "Keyboard"},
}


@tool
def get_order_status(order_id: str) -> dict:
    """Return the status of an order by its id, for example A100."""
    return ORDERS.get(order_id, {"error": f"order {order_id} not found"})


# Hands the chat to a person in the Kapso inbox (KAPSO_HANDOFF_USER_ID in .env).
# While the conversation is assigned, the bridge does not run the agent.
handoff = KapsoHumanHandoffTool(client=KapsoClient())

tools = [get_order_status, handoff]
model_with_tools = model.bind_tools(tools)


async def agent(state: MessagesState) -> dict:
    response = await model_with_tools.ainvoke([SystemMessage(SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")
# Each WhatsApp conversation becomes a LangGraph thread, so the checkpointer
# keeps the memory of every chat
graph = builder.compile(checkpointer=InMemorySaver())

# Reads KAPSO_API_KEY, KAPSO_PHONE_NUMBER_ID and KAPSO_WEBHOOK_SECRET from .env
bridge = KapsoBridge(graph, AsyncKapsoClient())
app = create_app(bridge)
