<h1 align="center">langchain-kapso</h1>

<p align="center">
  Run the LangGraph agent that answers your customers on WhatsApp, through <a href="https://kapso.ai">Kapso</a>.<br/>
  Kapso delivers the messages, your agent answers them, and a person takes over when needed.
</p>

> [!WARNING]
> Community integration, not affiliated with Kapso or LangChain.

## Features

- **WhatsApp bridge for LangGraph**: every customer message runs your graph and the reply goes back on WhatsApp. You never call `graph.invoke` yourself.
- **Memory per chat**: each Kapso conversation is a LangGraph thread, so a checkpointer gives every customer their own history.
- **Production details handled**: signed webhooks are verified, retried deliveries are skipped, Kapso gets a `200` right away while the agent runs in the background, and messages of the same chat are processed in order.
- **Human handoff**: the agent assigns the chat to a person in the Kapso inbox with a summary, stays quiet while they handle it, and takes over again when they unassign it.
- **Least privilege tools**: a small set of WhatsApp tools (send, read, hand off) that is safe to give an agent reading untrusted customer messages.
- **Sync and async client** for the Kapso WhatsApp and Platform APIs.

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

## Human handoff

The agent can hand a conversation to a person on your team. The conversation is
assigned to them in the Kapso inbox, and the bridge stops answering it until they
unassign it; then the agent takes over again with the same memory.

```python
from langchain_kapso import KapsoClient, KapsoHumanHandoffTool

# The team member who receives the chats, from client.list_users() (use "user_id")
handoff = KapsoHumanHandoffTool(client=KapsoClient(), handoff_user_id="...")
tools = [get_order_status, handoff]
```

The agent calls it with a short summary, which shows up as the assignment note,
so the person does not have to read the whole chat. You can also set
`KAPSO_HANDOFF_USER_ID` instead of passing `handoff_user_id`.

Nodes and tools can also read who they are talking to from the config, in
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
| `kapso_human_handoff` | Hand the conversation to a person (with `handoff_user_id`) |

WhatsApp only allows free-form messages within 24 hours of the customer's last
message; outside that window you need an approved template.

## Development

```bash
uv sync --all-extras
uv run pytest
```

## Status

Early version, tested end to end with the Kapso sandbox. See [TODO.md](TODO.md) for
what comes next: merging bursts of messages, the 24-hour window,
multimodal messages and prompt management.
