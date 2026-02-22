"""
User service — CRUD operations for the User aggregate.

Users are fetched without caching because the list is typically small
and the data changes infrequently; adding a cache layer here is a
straightforward future optimisation if profiling shows it is necessary.
"""
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas import UserCreate


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _user_to_dict(user: User) -> dict:
    """Serialise a User ORM instance to a plain dict (list view)."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "bio": user.bio,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _article_summary_to_dict(article) -> dict:
    """
    Serialise an Article to a lightweight summary dict suitable for
    embedding inside a UserDetail response.

    Author and tags are intentionally omitted to avoid circular nesting.
    """
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
        "author": None,
        "tags": [],
    }


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def get_users(db: AsyncSession) -> list[dict]:
    """
    Return all users ordered by creation date (newest first).

    Articles are not loaded in the list view to keep the payload lean.
    """
    q = select(User).order_by(User.created_at.desc())

    result = await db.execute(q)
    return [_user_to_dict(u) for u in result.scalars().all()]


async def get_user(db: AsyncSession, user_id: int) -> dict | None:
    """
    Return the full detail dict for *user_id* including a summary of
    their articles.

    Returns None when the user does not exist.
    ``selectinload`` is used for the articles relationship to issue a
    single additional query rather than N queries (N+1 prevention).
    """
    q = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.articles))
    )

    result = await db.execute(q)
    user = result.unique().scalar_one_or_none()
    if user is None:
        return None

    data = _user_to_dict(user)
    data["articles"] = [_article_summary_to_dict(a) for a in user.articles]
    return data


async def create_user(db: AsyncSession, data: UserCreate) -> dict:
    """
    Create a new user and return its serialised dict.

    Email and username uniqueness is enforced at the database level
    (unique constraints in the schema); the router is responsible for
    translating integrity errors into 409 responses.
    """
    user = User(
        username=data.username,
        email=data.email,
        display_name=data.display_name,
        bio=data.bio,
    )
    db.add(user)
    await db.flush()
    return _user_to_dict(user)
