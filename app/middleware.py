import time
from contextvars import ContextVar

from sqlalchemy import event
from starlette.types import ASGIApp, Receive, Scope, Send

# ---------------------------------------------------------------------------
# Per-request context variable
# ---------------------------------------------------------------------------

query_count_var: ContextVar[int] = ContextVar("query_count", default=0)


def install_query_counter(engine) -> None:
    """
    Register a ``before_cursor_execute`` event listener on *engine* that
    increments the per-request ``query_count_var`` for every SQL statement.

    This captures ALL queries including those issued internally by
    SQLAlchemy eager-loading strategies (``selectinload``, ``joinedload``).

    Must be called once per engine (production engine in ``database.py``,
    test engine in ``conftest.py``).
    """
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _count_query(conn, cursor, statement, parameters, context, executemany):
        query_count_var.set(query_count_var.get() + 1)


# ---------------------------------------------------------------------------
# Middleware (pure ASGI — avoids BaseHTTPMiddleware ContextVar isolation)
# ---------------------------------------------------------------------------

class TimingMiddleware:
    """
    Pure ASGI middleware that adds two diagnostic response headers:

    - ``X-Response-Time-Ms``: wall-clock time for the entire request.
    - ``X-Query-Count``: total SQL queries executed during the request,
      automatically counted via the SQLAlchemy engine event registered
      by ``install_query_counter``.

    Unlike ``BaseHTTPMiddleware``, this does NOT spawn a child asyncio
    task for the inner application, so ``ContextVar`` mutations are
    visible when we read the counter after the response has been sent.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Reset the per-request counter.
        query_count_var.set(0)
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                headers = list(message.get("headers", []))
                headers.append((b"x-response-time-ms", str(duration_ms).encode()))
                headers.append((b"x-query-count", str(query_count_var.get()).encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
