# langchain-kapso and the Kapso MCP

Kapso's [MCP server](https://docs.kapso.ai/docs/whatsapp/mcp) and this library solve
different problems, and work well together.

| | Kapso MCP | langchain-kapso |
| --- | --- | --- |
| Made for | Coding and operator agents (Claude Code, Cursor, Codex) that manage your Kapso project | The agent in production that answers your customers |
| Reacts when a customer writes | No, the agent has to start every action | Yes, each webhook runs your graph and sends the reply |
| Memory, ordering, retries, handoff pause | No | Yes |
| Tools given to the model | 184 tools, about 34k tokens per call | 5 tools, about 700 tokens |
| Destructive tools reachable with an API key | Yes, such as deleting contacts, sending broadcasts or editing webhooks | None |

Use the MCP in your editor to set up and operate Kapso, and langchain-kapso to run the
customer-facing agent.

## Why the MCP is not a runtime for customer-facing agents

- **Size**: every tool definition is sent to the model on every turn. Loading the full
  MCP adds about 34k tokens to each customer message, which means more cost, more
  latency and worse tool choices for small models. Even `send_whatsapp_message` alone is
  about 7k characters, since it covers every message type.
- **Security**: a server-side agent connects with a project API key, which has full
  access. An agent that reads messages from unknown customers is exposed to prompt
  injection, so it should only be able to call the few tools it needs.
- **No inbound loop**: an MCP client calls tools, it does not receive webhooks. Something
  still has to receive the customer's message, run the agent with that chat's memory
  and send the answer back. That is the bridge in this library.

## How the numbers were measured

Loading the MCP from LangChain with `langchain-mcp-adapters` and a project API key
(October 2026):

```python
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "kapso": {
        "transport": "streamable_http",
        "url": "https://api.kapso.ai/mcp",
        "headers": {"Authorization": f"Bearer {KAPSO_API_KEY}"},
    }
})
tools = await client.get_tools()  # 184 tools

size = sum(len(json.dumps(convert_to_openai_tool(t))) for t in tools)  # ~137k characters
```

The same measure for `KapsoToolkit(..., handoff_user_id=...).get_tools()` gives 5 tools
and about 2.8k characters. Token counts use the usual estimate of 4 characters per token.

The MCP exposes fewer tools when you connect with browser sign-in and grant limited
permissions; the numbers above are for an API key, which is how a server-side agent
connects.
