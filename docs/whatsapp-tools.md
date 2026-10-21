# WhatsApp tools

The bridge already sends the agent's answer to the customer, so a support agent usually
does not need these tools. They are for agents that act on WhatsApp on their own, such as:

- An assistant for your team that reads recent chats and summarizes them.
- An agent that sends reminders or follow-ups to customers.
- A support agent that needs to send reply buttons or hand off to a person.

## Setup

```python
from langchain_kapso import KapsoClient, KapsoToolkit

tools = KapsoToolkit(client=KapsoClient()).get_tools()
model_with_tools = model.bind_tools(tools)
```

Add `handoff_user_id="..."` to `KapsoToolkit` to include the handoff tool (see
[Human handoff](human-handoff.md)). With an `AsyncKapsoClient` passed as `async_client`,
the tools use it when the graph runs asynchronously.

## Tools

| Tool | Input | Returns |
| --- | --- | --- |
| `kapso_send_text` | `to` phone number, `body` | The id of the sent message |
| `kapso_send_buttons` | `to`, `body`, up to 3 `buttons` with `id` and `title` | The id of the sent message |
| `kapso_get_messages` | `conversation_id`, `limit` | The chat as a transcript, oldest first |
| `kapso_list_conversations` | optional `status`, `phone_number`, `limit` | Conversations with their last message |
| `kapso_human_handoff` | `summary` | Confirmation that the chat was handed off |

WhatsApp only allows free-form messages within 24 hours of the customer's last message.
Outside that window, sending fails and you need an approved template.
