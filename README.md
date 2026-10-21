<h1 align="center">langchain-kapso</h1>

<p align="center">
  Run the LangGraph agent that answers your customers on WhatsApp, through <a href="https://kapso.ai">Kapso</a>.<br/>
  Kapso delivers the messages, your agent answers them, and a person takes over when needed.
</p>

> [!WARNING]
> Community integration, not affiliated with Kapso or LangChain.

<p align="center">
  <img src="docs/architecture.png?v=7" alt="A customer writes on WhatsApp, Kapso sends the message to the langchain-kapso bridge on your server, the bridge runs your LangGraph agent and sends the reply back; the agent can hand the chat to a person in the Kapso inbox" width="100%"/>
</p>

## Why

Connecting a LangGraph agent to WhatsApp always takes the same glue code. Receive Kapso
webhooks, check their signature, skip retries, keep a memory per chat, answer in order and
stay quiet when a person takes over. Every team ends up writing it by hand.

This package packs that glue, so you write the agent and it handles the WhatsApp side.

## Features

- Connects any LangGraph graph to a Kapso WhatsApp number with a few lines of code.
- Uses each Kapso conversation as a LangGraph thread, so every customer keeps their own memory.
- Works with any LangGraph checkpointer, such as PostgreSQL, so every chat's memory survives restarts.
- Verifies webhook signatures, skips retried deliveries and processes the messages of each chat in order.
- Answers Kapso right away and runs the agent in the background, so slow replies do not trigger retries.
- Hands a chat to a person in the Kapso inbox and resumes the agent when they unassign it.
- Includes WhatsApp tools for LangChain agents to send messages, read conversations and hand off.
- Provides a sync and async client for the Kapso WhatsApp and Platform APIs.

## Install

```bash
uv add "langchain-kapso[server] @ git+https://github.com/pqbas/langchain-kapso"
# or: pip install "langchain-kapso[server] @ git+https://github.com/pqbas/langchain-kapso"
```

Set your credentials, from the Kapso dashboard:

```bash
KAPSO_API_KEY=...            # Integrations, API keys
KAPSO_PHONE_NUMBER_ID=...    # WhatsApp, Phone numbers
KAPSO_WEBHOOK_SECRET=...     # the secret of your webhook
```

## Quickstart

A LangGraph agent with memory, answering on WhatsApp. The graph is plain LangGraph;
the last three lines connect it to Kapso.

```python
# quickstart.py
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
```

You never call `graph.invoke` yourself. When a customer writes on WhatsApp, the bridge
runs the graph with that message and sends the answer back. If your agent follows
LangGraph's usual chat conventions, such as `MessagesState` or `create_agent`, it works as
is; see [what your graph needs](docs/bridge.md#what-your-graph-needs).

### Connect it to Kapso

1. Run the server.

   ```bash
   uvicorn quickstart:app --port 8000
   ```

2. Give it a public HTTPS URL. In production that is your deployed server. To try it on
   your machine, open a temporary tunnel instead, for example
   `cloudflared tunnel --url http://localhost:8000`.

3. In Kapso, add a webhook to your WhatsApp number for the `whatsapp.message.received`
   event, pointing to `https://<your-url>/webhooks/whatsapp`, with the same secret you set
   in `KAPSO_WEBHOOK_SECRET`.

Now write to your number on WhatsApp and the agent answers. A fuller example with tools
and human handoff is in [`examples/support_agent.py`](examples/support_agent.py).

## Docs

- [How the bridge works](docs/bridge.md): what happens with each message, and the customer data your agent receives.
- [Human handoff](docs/human-handoff.md): pass a chat to a person in the Kapso inbox and resume the agent afterwards.
- [Memory in PostgreSQL](docs/postgres.md): keep every chat's memory across restarts.
- [WhatsApp tools](docs/whatsapp-tools.md): let agents send messages, read conversations and hand off on their own.

## Development

```bash
uv sync --all-extras
uv run pytest
```

## Status

Early version, tested end to end with the Kapso sandbox. See [TODO.md](TODO.md) for
what comes next: merging bursts of messages, the 24-hour window,
multimodal messages and prompt management.
