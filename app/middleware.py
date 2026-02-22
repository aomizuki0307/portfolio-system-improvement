import time
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Per-request context variable
# ---------------------------------------------------------------------------

# Each asyncio Task (i.e. each request) gets its own isolated copy of this
# variable, so concurrent requests never interfere with each other's count.
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
# Middleware
# ---------------------------------------------------------------------------

class TimingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that adds two diagnostic response headers:

    - ``X-Response-Time-Ms``: wall-clock time for the entire request
      measured with ``time.perf_counter`` (sub-millisecond resolution).
    - ``X-Query-Count``: number of SQL queries executed during the
      request, as reported by ``increment_query_count`` calls in the
      service layer.

    Both headers are purely informational and safe to expose on an
    internal/staging environment.  Strip them at the reverse-proxy
    (nginx/ALB) boundary before serving public traffic if desired.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Reset the per-request counter before the handler runs.
        query_count_var.set(0)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        response.headers["X-Query-Count"] = str(query_count_var.get())
        return response
