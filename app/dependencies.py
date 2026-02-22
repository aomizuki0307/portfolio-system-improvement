from fastapi import Query

from app.config import settings


class PaginationParams:
    """
    Reusable FastAPI dependency that parses and validates pagination /
    sorting query parameters.

    Usage in a router::

        @router.get("/articles")
        async def list_articles(pagination: PaginationParams = Depends(PaginationParams)):
            ...

    Attributes
    ----------
    page:
        1-based page number (minimum 1).
    page_size:
        Number of items per page, clamped to ``settings.MAX_PAGE_SIZE``
        regardless of the value supplied by the caller.
    sort_by:
        ORM column name to sort by.  The service layer is responsible
        for validating that this maps to a real column before passing it
        to SQLAlchemy.
    sort_order:
        ``"asc"`` or ``"desc"`` (enforced by the regex pattern).
    offset:
        Computed SQL OFFSET derived from *page* and *page_size*.
    """

    def __init__(
        self,
        page: int = Query(
            1,
            ge=1,
            description="Page number (1-based).",
        ),
        page_size: int = Query(
            20,
            ge=1,
            le=100,
            description="Number of items returned per page (max 100).",
        ),
        sort_by: str = Query(
            "created_at",
            description="Column name to sort results by.",
        ),
        sort_order: str = Query(
            "desc",
            pattern="^(asc|desc)$",
            description="Sort direction: 'asc' or 'desc'.",
        ),
    ) -> None:
        self.page = page
        # Respect the application-level hard ceiling even if the schema
        # already validates le=100, so a settings change is sufficient.
        self.page_size = min(page_size, settings.MAX_PAGE_SIZE)
        self.sort_by = sort_by
        self.sort_order = sort_order

    @property
    def offset(self) -> int:
        """SQL OFFSET value computed from the current page and page size."""
        return (self.page - 1) * self.page_size
