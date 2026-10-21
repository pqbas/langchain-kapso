"""FastAPI app that receives Kapso webhooks. Install with ``langchain-kapso[server]``."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request, Response

from langchain_kapso.bridge import InvalidSignatureError, KapsoBridge

logger = logging.getLogger(__name__)


def create_app(
    bridge: KapsoBridge,
    path: str = "/webhooks/whatsapp",
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[Any]] | None = None,
) -> FastAPI:
    """Create an app that answers Kapso right away and runs the agent in the background.

    Answering fast matters: Kapso retries deliveries that fail or time out, and
    pauses webhooks that keep failing.

    ``lifespan`` runs code when the server starts and stops, for example to open
    a Postgres connection pool for the checkpointer. It is passed to FastAPI as is.
    """
    app = FastAPI(title="Kapso LangGraph webhook", lifespan=lifespan)

    async def _run(message):
        try:
            await bridge.process(message)
        except Exception:
            logger.exception("Agent failed for message %s", message.message_id)

    @app.post(path)
    async def webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
        raw_body = await request.body()
        try:
            messages = bridge.accept(raw_body, request.headers)
        except InvalidSignatureError:
            return Response("Invalid signature", status_code=401)
        for message in messages:
            background_tasks.add_task(_run, message)
        return Response("OK", status_code=200)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
