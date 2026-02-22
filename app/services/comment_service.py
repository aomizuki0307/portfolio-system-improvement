"""
Comment service — append-only comment creation for the Article aggregate.

Comments are intentionally simple: they cannot be edited or deleted via
the public API (a common design choice to prevent comment-history
manipulation).  All writes invalidate the parent article's cache entry
so the detail view stays consistent.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache
from app.middleware import increment_query_count
from app.models import Article, Comment
from app.schemas import CommentCreate


async def add_comment(
    db: AsyncSession,
    article_id: int,
    data: CommentCreate,
) -> dict | None:
    """
    Append a new comment to the article identified by *article_id*.

    Returns the serialised comment dict on success, or None when the
    target article does not exist.

    The parent article's cache entry (detail view) is invalidated so
    that the next read reflects the new comment count without serving
    stale data.
    """
    # Verify the article exists before creating the comment.
    q = select(Article).where(Article.id == article_id)
    increment_query_count()
    result = await db.execute(q)
    article = result.scalar_one_or_none()
    if article is None:
        return None

    comment = Comment(
        content=data.content,
        author_name=data.author_name,
        article_id=article_id,
    )
    db.add(comment)
    await db.flush()

    # Invalidate the detail cache so the next request loads fresh data.
    await cache.invalidate_article(article_id)

    return {
        "id": comment.id,
        "content": comment.content,
        "author_name": comment.author_name,
        "article_id": comment.article_id,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }
