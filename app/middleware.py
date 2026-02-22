import time
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

# ---------------------------------------------------------------------------
# Per-request context variable
# ---------------------------------------------------------------------------

# Each request gets its own isolated copy of this variable via
# copy_context(), so concurrent requests never interfere with each
# other's count.
query_count_var: ContextVar[int] = ContextVar("query_count", default=0)


def increment_query_count() -> None:
    """
    Increment the database-query counter for the current request.

    Call this once for every SQL statement executed inside a service
    function so that the middleware can expose the total via a response
    header for N+1 diagnosis and performance monitoring.
    """
    query_count_var.set(query_count_var.get() + 1)


# ---------------------------------------------------------------------------
# Middleware (pure ASGI — avoids BaseHTTPMiddleware ContextVar isolation)
# ---------------------------------------------------------------------------

class TimingMiddleware:
    """
    Pure ASGI middleware that adds two diagnostic response headers:

    - ``X-Response-Time-Ms``: wall-clock time for the entire request.
    - ``X-Query-Count``: number of SQL queries executed during the
      request, as reported by ``increment_query_count`` calls in the
      service layer.

    Unlike ``BaseHTTPMiddleware``, this does NOT spawn a child asyncio
    task for the inner application, so ``ContextVar`` mutations made by
    route handlers and service functions are visible when we read the
    counter after the response has been sent.
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
