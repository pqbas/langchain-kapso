# Memory in PostgreSQL

The memory of each chat is the LangGraph checkpointer, so moving it to PostgreSQL only
changes how the graph is compiled. Chats then survive restarts and deploys.

```bash
uv add langgraph-checkpoint-postgres "psycopg[binary,pool]"
```

`AsyncPostgresSaver` has to be created once the server is running, so the graph is
compiled in the app's `lifespan` and assigned to the bridge:

```python
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

bridge = KapsoBridge(None, AsyncKapsoClient())  # the graph is set at startup


@asynccontextmanager
async def lifespan(app):
    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        await checkpointer.setup()  # creates the checkpoint tables the first time
        bridge.graph = builder.compile(checkpointer=checkpointer)
        yield


app = create_app(bridge, lifespan=lifespan)
```

The full example is in [`examples/postgres.py`](../examples/postgres.py).

## Running more than one server

This setup is safe with one server process. Retried deliveries and the order of messages
per chat are still tracked in memory, so with several workers a retry could be processed
twice and two messages of the same chat could run at the same time. A shared store for
both is on the [TODO](../TODO.md).
