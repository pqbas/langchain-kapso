# Use WhatsApp as a tool

Besides answering through the bridge, any LangChain agent can use WhatsApp through these tools.

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
