# How the bridge works

`KapsoBridge` is the piece that turns your LangGraph graph into the agent that answers
on WhatsApp. You give it a compiled graph and a Kapso client, and `create_app` exposes it
as a web server that Kapso calls for every customer message.

## What happens with each message

1. Kapso sends the message to `POST /webhooks/whatsapp`.
2. The bridge checks the `X-Webhook-Signature` with your `KAPSO_WEBHOOK_SECRET` and
   answers `401` if it does not match.
3. If Kapso already delivered this message before (same `X-Idempotency-Key`), it is
   ignored, so a retry never produces a second answer.
4. Kapso gets a `200` right away. The agent runs in the background, because Kapso retries
   deliveries that take too long.
5. If the conversation is assigned to a person in the Kapso inbox, the bridge stops here
   (see [Human handoff](human-handoff.md)).
6. The message is marked as read and the customer sees "typing…".
7. The graph runs with `thread_id` set to the Kapso conversation id, so it continues that
   customer's history. Messages of the same chat run one at a time, in order.
8. The last AI message of the result is sent to the customer.

## What your graph needs

The agent can be anything you build with LangGraph, from a single node to tools, RAG or
several agents with a supervisor, including agents made with LangChain's `create_agent`.
The bridge only needs three things from it.

| Requirement | Why | If your graph is different |
| --- | --- | --- |
| The state has a `messages` key, like `MessagesState` | The customer's message arrives as `{"messages": [HumanMessage(text)]}` | Not configurable yet; a custom input builder is on the [TODO](../TODO.md) |
| The answer ends up as the last `AIMessage` in `messages` | That message is what the customer receives | Pass a `reply_extractor` that returns the text to send |
| Compiled with a checkpointer (recommended) | Gives each chat its memory between messages | Without one the agent works, but every message starts from scratch |

```python
# Answer stored somewhere else in the state
bridge = KapsoBridge(graph, AsyncKapsoClient(), reply_extractor=lambda state: state["final_answer"])
```

If `reply_extractor` returns nothing, no message is sent, which lets a graph decide to stay
quiet.

## Who the agent is talking to

Every run gets these values in `config["configurable"]`, so nodes and tools can use them:

| Key | Value |
| --- | --- |
| `thread_id`, `kapso_conversation_id` | The Kapso conversation id |
| `kapso_phone_number` | The customer's phone number |
| `kapso_contact_name` | The customer's WhatsApp name, when available |

```python
from langchain_core.runnables import RunnableConfig


def agent(state: MessagesState, config: RunnableConfig) -> dict:
    name = config["configurable"].get("kapso_contact_name")
    ...
```

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `webhook_secret` | `KAPSO_WEBHOOK_SECRET` | Secret used to verify webhooks |
| `typing_indicator` | `True` | Show "typing…" while the agent works |
| `pause_when_assigned` | `True` | Do not answer chats assigned to a person |
| `reply_extractor` | last AI message | Function that picks the text to send from the graph result |
