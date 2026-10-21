"""The quickstart agent with its memory in PostgreSQL, so chats survive restarts.

Install the Postgres checkpointer:
    uv add langgraph-checkpoint-postgres "psycopg[binary,pool]"

Run it (DATABASE_URL in .env, e.g. postgresql://user:pass@localhost:5432/agent):
    uv run uvicorn examples.postgres:app --port 8000
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
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

# The graph is compiled at startup, once the Postgres connection is open
bridge = KapsoBridge(None, AsyncKapsoClient())


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
        await checkpointer.setup()  # creates the checkpoint tables the first time
        bridge.graph = builder.compile(checkpointer=checkpointer)
        yield


app = create_app(bridge, lifespan=lifespan)
