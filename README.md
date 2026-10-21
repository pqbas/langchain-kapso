# langchain-kapso

Connect LangChain and LangGraph agents to WhatsApp through [Kapso](https://kapso.ai).

> [!WARNING]
> Community integration, not affiliated with Kapso or LangChain.

- **Bridge**: receive Kapso webhooks, run your LangGraph graph and reply on WhatsApp.
  Each WhatsApp conversation is a LangGraph thread, so a checkpointer gives every
  chat its own memory.
- **Tools**: let any agent send messages, send reply buttons, read a conversation and
  list conversations.
- **Client**: a small sync and async client for the Kapso WhatsApp API.

## Install

```bash
uv add "langchain-kapso[server] @ git+https://github.com/pqbas/langchain-kapso"
# or: pip install "langchain-kapso[server] @ git+https://github.com/pqbas/langchain-kapso"
```

Set your credentials, from the Kapso dashboard:

```bash
KAPSO_API_KEY=...            # Integrations → API keys
KAPSO_PHONE_NUMBER_ID=...    # WhatsApp → Phone numbers
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

## How it works

For every customer message the bridge:

1. Verifies the `X-Webhook-Signature` and skips retried deliveries (`X-Idempotency-Key`).
2. Answers Kapso with `200` right away and runs the agent in the background, since
   Kapso retries slow or failed deliveries.
3. Marks the message as read and shows the typing indicator.
4. Calls `graph.ainvoke` with `thread_id` set to the Kapso conversation id. Messages
   of the same conversation run one at a time and in order.
5. Sends the last AI message back to the customer.

Nodes and tools can read who they are talking to from the config, in
`config["configurable"]["kapso_phone_number"]` and `["kapso_contact_name"]`.

## Use WhatsApp as a tool

```python
from langchain_kapso import KapsoClient, KapsoToolkit

tools = KapsoToolkit(client=KapsoClient()).get_tools()
model_with_tools = model.bind_tools(tools)
```

| Tool | What it does |
| --- | --- |
| `kapso_send_text` | Send a text message |
| `kapso_send_buttons` | Send up to 3 reply buttons |
| `kapso_get_messages` | Read a conversation as a transcript |
| `kapso_list_conversations` | List conversations with their last message |

WhatsApp only allows free-form messages within 24 hours of the customer's last
message; outside that window you need an approved template.

## Development

```bash
uv sync --all-extras
uv run pytest
```

## Status

Early version, tested end to end with the Kapso sandbox. See [TODO.md](TODO.md) for
what comes next: human handoff, merging bursts of messages, the 24-hour window,
multimodal messages and prompt management.
