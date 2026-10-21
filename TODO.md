# TODO

Ideas for the next versions, roughly in priority order.

## Long replies and media

Kapso's official adapters (Hermes Agent, OpenClaw, Chat SDK) already handle these.

- [ ] Split replies longer than WhatsApp's text limit into several messages, so a long answer from the agent does not fail.
- [ ] Send images, audio, video and documents from the agent, not only text.

## Human handoff

- [x] `kapso_human_handoff` tool: the agent calls it when a case needs a person, with a short summary for the operator.
- [x] The bridge stops answering a conversation while it is in handoff, so the AI never replies on top of a human in the Kapso inbox.
- [x] A way to give the conversation back to the agent: unassign it in the Kapso inbox or call `unassign_conversation`; the agent resumes the same LangGraph thread.
- Built on Kapso conversation assignments, since Kapso's native handoff only applies to Kapso workflows. The bridge checks the assignment on each message (one API call).
- [ ] React to assignment changes through webhooks instead of checking on every message, if Kapso exposes such an event.

## Bursts of messages

- [ ] Merge the messages of a buffered batch (and messages that arrive while the agent is answering) into a single turn, instead of one agent run per message.
- [ ] Document how to combine it with Kapso's webhook buffering (`buffer_enabled`, `buffer_window_seconds`).

## 24-hour customer service window

- [ ] Detect the "outside the 24-hour window" error and raise a clear `WindowClosedError`.
- [ ] Optional fallback: send an approved template to reopen the conversation.
- [ ] Template support in the client and as a tool (`kapso_send_template`).

## Graph input

- [ ] `input_builder` option in `KapsoBridge`, to build any graph input from the WhatsApp message, for graphs whose state has no `messages` key.

## Session data in the graph

- [ ] Optional state preset (`KapsoMessagesState`) with phone number, contact name, conversation id and new-conversation flag, filled by the bridge, besides the current `config["configurable"]` values.

## Multimodal messages

- [ ] Audio: use Kapso's transcript (`message.kapso.transcript`) as the message text, marked as a voice note.
- [ ] Images: download the media through Kapso and pass it to the model as an image content block, with the caption as text.
- [ ] Documents and locations: readable text representation for the agent.
- [ ] `kapso_get_messages` returns media in the same LLM-friendly format.

## Prompt management (LLMOps hook)

- [ ] Let the bridge load the system prompt from a registry (LangSmith Prompt Hub, Langfuse) with a short cache, so editing the prompt in one place updates every deployed agent without a redeploy.
- [ ] Tag each run with the prompt version for tracing and evals.

## Streaming in chunks

- [ ] Optional mode that streams tokens from the graph and sends a WhatsApp message per paragraph, to cut perceived latency. Paragraphs rather than sentences, so it does not feel like spam.

## Reliability and packaging

- [ ] Log every reply sent, and failures with the conversation id.
- [x] Persistent memory with PostgreSQL (`docs/postgres.md`, `lifespan` in `create_app`).
- [ ] Pluggable store for processed webhook keys and per-chat locks (Redis, Postgres), so several workers can run at once.
- [ ] Send to business-scoped user ids (`recipient`) when there is no phone number.
- [ ] Publish to PyPI and add CI (tests and type checks on each push).
