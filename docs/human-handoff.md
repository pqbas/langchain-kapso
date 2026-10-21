# Human handoff

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
