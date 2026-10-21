# Memory in PostgreSQL

By default the examples keep each chat's memory in `InMemorySaver`, which is lost when the
server restarts. To keep it, use LangGraph's PostgreSQL checkpointer. The bridge does not
change; only the way the graph is compiled does.

## Setup

1. Install the checkpointer:

   ```bash
   uv add langgraph-checkpoint-postgres "psycopg[binary,pool]"
   ```

2. Add your database to `.env`:

   ```bash
   DATABASE_URL=postgresql://user:password@localhost:5432/agent
   ```

3. Compile the graph when the server starts. `AsyncPostgresSaver` needs the server to be
   running, so instead of passing the graph to the bridge right away, pass `None` and set
   it in the app's `lifespan`:

   ```python
   import os
   from contextlib import asynccontextmanager

   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

   bridge = KapsoBridge(None, AsyncKapsoClient())  # the graph is set at startup


   @asynccontextmanager
   async def lifespan(app):
       async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
           await checkpointer.setup()  # creates the tables the first time
           bridge.graph = builder.compile(checkpointer=checkpointer)
           yield


   app = create_app(bridge, lifespan=lifespan)
   ```

The full example is in [`examples/postgres.py`](../examples/postgres.py). Any other LangGraph
checkpointer, such as SQLite or Redis, works the same way.

## Running more than one server

This setup is safe with one server process. Retried deliveries and the order of messages
per chat are still tracked in memory, so with several workers a retry could be processed
twice and two messages of the same chat could run at the same time. A shared store for
both is on the [TODO](../TODO.md).
