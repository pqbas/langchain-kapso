# langchain-kapso

Connect LangChain and LangGraph agents to WhatsApp through [Kapso](https://kapso.ai).

- **Bridge**: receive Kapso webhooks, run your LangGraph graph and reply on WhatsApp.
  Each WhatsApp conversation is a LangGraph thread, so a checkpointer gives every
  chat its own memory.
- **Tools**: let any agent send messages, send reply buttons, read a conversation and
  list conversations.
- **Client**: a small sync and async client for the Kapso WhatsApp API.

## Install

```bash
uv add "langchain-kapso[server]"   # or: pip install "langchain-kapso[server]"
```

Set your credentials, from the Kapso dashboard:

```bash
KAPSO_API_KEY=...            # Integrations → API keys
KAPSO_PHONE_NUMBER_ID=...    # WhatsApp → Phone numbers
KAPSO_WEBHOOK_SECRET=...     # the secret of your webhook
```

## Put a LangGraph agent on WhatsApp

```python
from langchain_kapso import AsyncKapsoClient, KapsoBridge
from langchain_kapso.server import create_app

graph = builder.compile(checkpointer=InMemorySaver())  # any graph with a "messages" key

bridge = KapsoBridge(graph, AsyncKapsoClient())
app = create_app(bridge)  # FastAPI app with POST /webhooks/whatsapp
```

```bash
uvicorn my_agent:app --port 8000
```

Expose the port (for example `cloudflared tunnel --url http://localhost:8000`) and
create a webhook in Kapso for `whatsapp.message.received` pointing to
`https://<your-host>/webhooks/whatsapp`.

For every customer message the bridge:

1. Verifies the `X-Webhook-Signature` and ignores retried deliveries (`X-Idempotency-Key`).
2. Answers Kapso with `200` right away and runs the agent in the background, since
   Kapso retries slow or failed deliveries.
3. Marks the message as read and shows the typing indicator.
4. Calls `graph.ainvoke` with `thread_id` set to the Kapso conversation id. Messages
   of the same conversation run one at a time and in order.
5. Sends the last AI message back to the customer.

Nodes and tools can read who they are talking to from the config:

```python
def agent(state: MessagesState, config: RunnableConfig) -> dict:
    phone = config["configurable"]["kapso_phone_number"]
    name = config["configurable"]["kapso_contact_name"]
```

A complete example is in [`examples/support_agent.py`](examples/support_agent.py).

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

Early version. Next steps: templates and media messages, sending to business-scoped
user ids, and a persistent store for processed webhook keys.
