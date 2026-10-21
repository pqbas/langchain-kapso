"""Smallest example: a LangGraph agent with memory, answering on WhatsApp.

Run it:
    uv run --extra server --group examples uvicorn examples.quickstart:app --port 8000
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from langchain_kapso import AsyncKapsoClient, KapsoBridge
from langchain_kapso.server import create_app

load_dotenv()

model = init_chat_model("anthropic:claude-haiku-5-5")

SYSTEM_PROMPT = "You are the support agent of an online store. Answer briefly and kindly."


def agent(state: MessagesState) -> dict:
    history_chat = [SystemMessage(SYSTEM_PROMPT)] + state["messages"]
    response = model.invoke(history_chat)
    return {"messages": [response]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)
graph = builder.compile(checkpointer=InMemorySaver())


# The new part: connect the graph to WhatsApp.
# thread_id = the Kapso conversation id, so every chat keeps its own memory
bridge = KapsoBridge(graph, AsyncKapsoClient())
app = create_app(bridge)  # receives messages on POST /webhooks/whatsapp
