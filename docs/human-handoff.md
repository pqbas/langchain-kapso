# Human handoff

Lets the agent pass a chat to a person on your team, for example when the customer asks
for a human or the agent cannot solve the case. The person answers from the Kapso inbox,
and the agent stays quiet until they give the chat back.

It is built on Kapso conversation assignments, so it only works for agents running
through the [bridge](bridge.md).

## Setup

1. Find the person who will receive the chats. Their id is the `user_id` field (not `id`)
   of the project members:

   ```python
   from langchain_kapso import KapsoClient

   for member in KapsoClient().list_users()["data"]:
       print(member["name"], member["user_id"])
   ```

2. Save it as `KAPSO_HANDOFF_USER_ID` in your `.env`, or pass it as `handoff_user_id`.

3. Add the tool to your agent's tools, next to your own:

   ```python
   from langchain_kapso import KapsoClient, KapsoHumanHandoffTool

   handoff = KapsoHumanHandoffTool(client=KapsoClient())
   tools = [get_order_status, handoff]  # get_order_status stands for your own tools
   model_with_tools = model.bind_tools(tools)
   ```

4. Tell the agent when to use it in the system prompt, for example "If the customer asks
   for a person or you cannot help, hand the conversation off."

## What happens

1. The agent calls `kapso_human_handoff` with a short summary of the case.
2. The chat is assigned to that person in the Kapso inbox, with the summary as the note,
   so they do not have to read the whole conversation.
3. The agent tells the customer that a person will continue.
4. While the chat is assigned, the bridge does not run the agent and leaves new messages
   unread, so the person sees them as new.
5. When the person unassigns the chat in the inbox, the next message goes to the agent
   again, with the history it had before the handoff.

The messages exchanged between the customer and the person are not part of the agent's
memory, since they never went through the graph. If the agent needs them, it can read
the chat with the `kapso_get_messages` tool.

You can also give a chat back from code with `client.unassign_conversation(conversation_id)`.

The bridge checks the assignment with one call to the Kapso API per incoming message.
