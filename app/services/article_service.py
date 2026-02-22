"""
Article service — business logic for the Article aggregate.

Design notes
------------
- All list/detail reads go through the cache-aside pattern (Redis →
  fallback to DB).  Cache keys encode every dimension that affects the
  result so stale data is never served.
- Eager loading via ``joinedload`` (many-to-one: author) and
  ``selectinload`` (one-to-many / many-to-many: tags, comments) is used
  throughout to eliminate N+1 queries.  The ``unique()`` call is
  required after any query that uses ``joinedload`` with collections to
  deduplicate the joined rows that SQLAlchemy returns.
- ``increment_query_count()`` is called once per ``db.execute`` so the
  ``TimingMiddleware`` can surface the total in the ``X-Query-Count``
  response header.
- Service functions flush but do not commit; the transaction boundary
  is owned by the ``get_db`` dependency in the router layer.
"""
import math
import re
import time
from datetime import datetime, timezone

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.cache import cache
from app.config import settings
from app.middleware import increment_query_count
from app.models import Article, Comment, Tag
from app.schemas import ArticleCreate, ArticleUpdate, PaginatedResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_STRIP_RE = re.compile(r"[^\w\s-]")
_SLUG_SPACE_RE = re.compile(r"[\s_]+")
_SLUG_DASH_RE = re.compile(r"-+")

# Columns that are safe to sort by; guards against arbitrary attribute access.
_SORTABLE_COLUMNS: frozenset[str] = frozenset(
    {"created_at", "published_at", "view_count", "title"}
)


def slugify(text: str) -> str:
    """Return a URL-safe, lowercase slug derived from *text*."""
    text = _SLUG_STRIP_RE.sub("", text.lower().strip())
    text = _SLUG_SPACE_RE.sub("-", text)
    return _SLUG_DASH_RE.sub("-", text).strip("-")


def _resolve_sort_column(sort_by: str):
    """
    Return the SQLAlchemy column expression for *sort_by*.

    Falls back to ``Article.created_at`` for any unrecognised or
    potentially dangerous column name.
    """
    if sort_by in _SORTABLE_COLUMNS:
        return getattr(Article, sort_by)
    return Article.created_at


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _serialize_user(author) -> dict | None:
    if author is None:
        return None
    return {
        "id": author.id,
        "username": author.username,
        "email": author.email,
        "display_name": author.display_name,
        "bio": author.bio,
        "created_at": author.created_at.isoformat() if author.created_at else None,
    }


def _article_to_dict(article: Article) -> dict:
    """Serialise an Article ORM instance to a plain dict (list view)."""
    return {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "summary": article.summary,
        "view_count": article.view_count,
        "is_published": article.is_published,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "user_id": article.user_id,
        "author": _serialize_user(article.author),
        "tags": [{"id": t.id, "name": t.name} for t in article.tags],
    }


def _article_detail_to_dict(article: Article) -> dict:
    """Serialise an Article ORM instance to a plain dict (detail view)."""
    data = _article_to_dict(article)
    data["content"] = article.content
    data["comments"] = [
        {
            "id": c.id,
            "content": c.content,
            "author_name": c.author_name,
            "article_id": c.article_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in article.comments
    ]
    return data


# ---------------------------------------------------------------------------
# Tag resolution helper (used by create / update)
# ---------------------------------------------------------------------------

async def _resolve_tags(db: AsyncSession, tag_names: list[str]) -> list[Tag]:
    """
    Return Tag ORM instances for each name in *tag_names*, creating any
    that do not yet exist.  All inserts are flushed within the caller's
    transaction.
    """
    tags: list[Tag] = []
    for name in tag_names:
        result = await db.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            await db.flush()
        tags.append(tag)
    return tags


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def get_articles(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> PaginatedResponse:
    """
    Return a paginated list of published articles, using Redis as a
    cache layer.

    Two SQL statements are issued on a cache miss:
    1. COUNT — total published articles.
    2. SELECT with LIMIT/OFFSET, author JOIN, and tags/comments LOAD.
    """
    cache_key = f"articles:list:{page}:{page_size}:{sort_by}:{sort_order}"
    cached = await cache.get(cache_key)
    if cached:
        return PaginatedResponse(**cached)

    # 1. Total count
    count_q = (
        select(func.count())
        .select_from(Article)
        .where(Article.is_published.is_(True))
    )
    increment_query_count()
    total: int = (await db.execute(count_q)).scalar_one()

    # 2. Paginated rows with eager-loaded relationships
    sort_col = _resolve_sort_column(sort_by)
    order_expr = desc(sort_col) if sort_order == "desc" else asc(sort_col)

    articles_q = (
        select(Article)
        .where(Article.is_published.is_(True))
        .options(joinedload(Article.author), selectinload(Article.tags))
        .order_by(order_expr)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    increment_query_count()
    result = await db.execute(articles_q)
    articles = result.unique().scalars().all()

    response = PaginatedResponse(
        items=[_article_to_dict(a) for a in articles],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )
    await cache.set(cache_key, response.model_dump(), ttl=settings.CACHE_TTL_LIST)
    return response


async def get_article(db: AsyncSession, article_id: int) -> dict | None:
    """
    Return the full detail dict for *article_id* (including content and
    comments), incrementing the view counter on each hit.

    Returns None when the article does not exist.
    """
    cache_key = f"articles:detail:{article_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    q = (
        select(Article)
        .where(Article.id == article_id)
        .options(
            joinedload(Article.author),
            selectinload(Article.tags),
            selectinload(Article.comments),
        )
    )
    increment_query_count()
    result = await db.execute(q)
    article = result.unique().scalar_one_or_none()
    if article is None:
        return None

    # Increment view count and flush within the current transaction.
    article.view_count += 1
    increment_query_count()
    await db.flush()

    data = _article_detail_to_dict(article)
    await cache.set(cache_key, data, ttl=settings.CACHE_TTL_DETAIL)
    return data


async def create_article(db: AsyncSession, data: ArticleCreate) -> dict:
    """
    Create a new article and return its full detail dict.

    Ensures slug uniqueness by appending a Unix timestamp suffix on
    collision (rare but possible for identical titles).
    """
    slug = slugify(data.title)
    existing = await db.execute(select(Article).where(Article.slug == slug))
    if existing.scalar_one_or_none() is not None:
        slug = f"{slug}-{int(time.time())}"

    article = Article(
        title=data.title,
        slug=slug,
        content=data.content,
        summary=data.summary,
        is_published=data.is_published,
        user_id=data.user_id,
    )

    if data.tags:
        article.tags.extend(await _resolve_tags(db, data.tags))

    if data.is_published:
        article.published_at = datetime.now(timezone.utc)

    db.add(article)
    await db.flush()
    await db.refresh(article, ["author", "tags", "comments"])

    await cache.invalidate_article()
    return _article_detail_to_dict(article)


async def update_article(
    db: AsyncSession, article_id: int, data: ArticleUpdate
) -> dict | None:
    """
    Partially update an existing article and return its updated detail dict.

    Returns None when the article does not exist.
    Only fields explicitly set in the request payload are modified
    (``model_dump(exclude_unset=True)``).
    """
    q = (
        select(Article)
        .where(Article.id == article_id)
        .options(
            joinedload(Article.author),
            selectinload(Article.tags),
            selectinload(Article.comments),
        )
    )
    increment_query_count()
    result = await db.execute(q)
    article = result.unique().scalar_one_or_none()
    if article is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    tags_data: list[str] | None = update_data.pop("tags", None)

    for field, value in update_data.items():
        setattr(article, field, value)

    # Re-generate slug if the title changed.
    if "title" in update_data:
        article.slug = slugify(update_data["title"])

    # Set published_at the first time the article is published.
    if data.is_published and not article.published_at:
        article.published_at = datetime.now(timezone.utc)

    if tags_data is not None:
        article.tags.clear()
        article.tags.extend(await _resolve_tags(db, tags_data))

    await db.flush()
    await cache.invalidate_article(article_id)
    return _article_detail_to_dict(article)


async def delete_article(db: AsyncSession, article_id: int) -> bool:
    """
    Delete the article identified by *article_id*.

    Returns True on success, False when the article does not exist.
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if article is None:
        return False

    await db.delete(article)
    await db.flush()
    await cache.invalidate_article(article_id)
    return True
