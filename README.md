<h1 align="center">langchain-kapso</h1>

<p align="center">
  Run the LangGraph agent that answers your customers on WhatsApp, through <a href="https://kapso.ai">Kapso</a>.<br/>
  Kapso delivers the messages, your agent answers them, and a person takes over when needed.
</p>

> [!WARNING]
> Community integration, not affiliated with Kapso or LangChain.

## Features

- Every customer message on WhatsApp runs your LangGraph graph, and the reply goes back to the customer.
- Each Kapso conversation is a LangGraph thread, so every customer keeps their own memory.
- Signed webhooks are verified, retried deliveries are skipped and messages of the same chat are processed in order.
- Kapso gets a `200` right away while the agent runs in the background.
- The agent can hand a chat to a person in the Kapso inbox, stays quiet while they handle it and takes over again when they unassign it.
- A small set of WhatsApp tools that is safe to give an agent reading untrusted customer messages.
- Sync and async client for the Kapso WhatsApp and Platform APIs.

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

```bash
uvicorn quickstart:app --port 8000
```

You never call `graph.invoke` yourself: when a customer writes on WhatsApp, the
bridge invokes the graph with that message and sends the answer back.

To receive messages, expose the port (for example `cloudflared tunnel --url http://localhost:8000`)
and add a webhook in Kapso for `whatsapp.message.received` pointing to
`https://<your-host>/webhooks/whatsapp`. A fuller example with tools is in
[`examples/support_agent.py`](examples/support_agent.py).

## Docs

- [Human handoff](docs/human-handoff.md): hand a chat to a person in the Kapso inbox and resume the agent afterwards.
- [WhatsApp tools](docs/whatsapp-tools.md): let any agent send messages, read conversations and hand off.
- [langchain-kapso and the Kapso MCP](docs/kapso-mcp.md): when to use each one.

## Development

```bash
uv sync --all-extras
uv run pytest
```

## Status

Early version, tested end to end with the Kapso sandbox. See [TODO.md](TODO.md) for
what comes next: merging bursts of messages, the 24-hour window,
multimodal messages and prompt management.
