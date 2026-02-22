"""
Direct service-layer tests — exercises business logic without HTTP overhead.

These tests call service functions directly with a database session, giving
accurate coverage of the SQLAlchemy query paths, cache-aside logic, and
serialisation helpers that the ASGI-transport-based endpoint tests miss
due to coverage instrumentation limitations with BaseHTTPMiddleware.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas import ArticleCreate, ArticleUpdate, CommentCreate, UserCreate
from app.services import article_service, comment_service, user_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(db: AsyncSession, username: str = "svcuser", email: str = "svc@example.com") -> User:
    user = User(username=username, email=email, display_name="Service User")
    db.add(user)
    await db.flush()
    return user


# ---------------------------------------------------------------------------
# article_service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_articles_empty(db_session: AsyncSession):
    result = await article_service.get_articles(db_session)
    assert result.total == 0
    assert result.items == []
    assert result.pages == 0


@pytest.mark.asyncio
async def test_create_article_via_service(db_session: AsyncSession):
    user = await _create_user(db_session)
    data = ArticleCreate(
        title="Service Test Article",
        content="Direct service test content",
        summary="Summary",
        is_published=True,
        user_id=user.id,
        tags=["python", "fastapi"],
    )
    result = await article_service.create_article(db_session, data)
    assert result["title"] == "Service Test Article"
    assert result["slug"] == "service-test-article"
    assert result["content"] == "Direct service test content"
    assert result["is_published"] is True
    assert result["published_at"] is not None
    # Tags are verified via get_article (refresh + noload doesn't re-populate)
    detail = await article_service.get_article(db_session, result["id"])
    assert detail is not None
    assert len(detail["tags"]) == 2


@pytest.mark.asyncio
async def test_create_article_without_tags_via_service(db_session: AsyncSession):
    user = await _create_user(db_session)
    data = ArticleCreate(
        title="No Tags",
        content="Content",
        is_published=False,
        user_id=user.id,
    )
    result = await article_service.create_article(db_session, data)
    assert result["tags"] == []
    assert result["published_at"] is None


@pytest.mark.asyncio
async def test_create_article_duplicate_slug(db_session: AsyncSession):
    user = await _create_user(db_session)
    data = ArticleCreate(title="Same Title", content="A", is_published=True, user_id=user.id)
    r1 = await article_service.create_article(db_session, data)
    data2 = ArticleCreate(title="Same Title", content="B", is_published=True, user_id=user.id)
    r2 = await article_service.create_article(db_session, data2)
    assert r1["slug"] != r2["slug"]


@pytest.mark.asyncio
async def test_get_articles_with_data(db_session: AsyncSession):
    user = await _create_user(db_session)
    for i in range(3):
        await article_service.create_article(
            db_session,
            ArticleCreate(
                title=f"Article {i}",
                content=f"Content {i}",
                is_published=True,
                user_id=user.id,
            ),
        )
    result = await article_service.get_articles(db_session, page=1, page_size=2)
    assert result.total == 3
    assert len(result.items) == 2
    assert result.pages == 2


@pytest.mark.asyncio
async def test_get_articles_sort_order(db_session: AsyncSession):
    user = await _create_user(db_session)
    await article_service.create_article(
        db_session, ArticleCreate(title="Alpha", content="C", is_published=True, user_id=user.id)
    )
    await article_service.create_article(
        db_session, ArticleCreate(title="Bravo", content="C", is_published=True, user_id=user.id)
    )
    result_asc = await article_service.get_articles(db_session, sort_by="title", sort_order="asc")
    titles = [a["title"] for a in result_asc.items]
    assert titles == sorted(titles)


@pytest.mark.asyncio
async def test_get_articles_invalid_sort_column(db_session: AsyncSession):
    """Invalid sort column falls back to created_at."""
    user = await _create_user(db_session)
    await article_service.create_article(
        db_session, ArticleCreate(title="Fallback", content="C", is_published=True, user_id=user.id)
    )
    result = await article_service.get_articles(db_session, sort_by="nonexistent_column")
    assert result.total == 1


@pytest.mark.asyncio
async def test_get_article_detail(db_session: AsyncSession):
    user = await _create_user(db_session)
    created = await article_service.create_article(
        db_session,
        ArticleCreate(
            title="Detail Article",
            content="Detailed content",
            is_published=True,
            user_id=user.id,
            tags=["test"],
        ),
    )
    detail = await article_service.get_article(db_session, created["id"])
    assert detail is not None
    assert detail["title"] == "Detail Article"
    assert detail["content"] == "Detailed content"
    assert detail["view_count"] == 1  # incremented on read
    assert detail["author"] is not None
    assert detail["author"]["username"] == "svcuser"


@pytest.mark.asyncio
async def test_get_article_not_found(db_session: AsyncSession):
    result = await article_service.get_article(db_session, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_update_article_via_service(db_session: AsyncSession):
    user = await _create_user(db_session)
    created = await article_service.create_article(
        db_session,
        ArticleCreate(title="Before Update", content="Old", is_published=True, user_id=user.id),
    )
    updated = await article_service.update_article(
        db_session,
        created["id"],
        ArticleUpdate(title="After Update", content="New"),
    )
    assert updated is not None
    assert updated["title"] == "After Update"
    assert updated["slug"] == "after-update"
    assert updated["content"] == "New"


@pytest.mark.asyncio
async def test_update_article_tags_via_service(db_session: AsyncSession):
    user = await _create_user(db_session)
    created = await article_service.create_article(
        db_session,
        ArticleCreate(title="Tag Update", content="C", is_published=True, user_id=user.id, tags=["old"]),
    )
    updated = await article_service.update_article(
        db_session, created["id"], ArticleUpdate(tags=["new-a", "new-b"])
    )
    assert updated is not None
    tag_names = {t["name"] for t in updated["tags"]}
    assert tag_names == {"new-a", "new-b"}


@pytest.mark.asyncio
async def test_update_article_publish(db_session: AsyncSession):
    user = await _create_user(db_session)
    created = await article_service.create_article(
        db_session,
        ArticleCreate(title="Draft", content="C", is_published=False, user_id=user.id),
    )
    assert created["published_at"] is None
    updated = await article_service.update_article(
        db_session, created["id"], ArticleUpdate(is_published=True)
    )
    assert updated is not None
    assert updated["published_at"] is not None


@pytest.mark.asyncio
async def test_update_nonexistent_article_service(db_session: AsyncSession):
    result = await article_service.update_article(
        db_session, 99999, ArticleUpdate(title="Ghost")
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_article_via_service(db_session: AsyncSession):
    user = await _create_user(db_session)
    created = await article_service.create_article(
        db_session,
        ArticleCreate(title="To Delete", content="C", is_published=True, user_id=user.id),
    )
    assert await article_service.delete_article(db_session, created["id"]) is True
    assert await article_service.get_article(db_session, created["id"]) is None


@pytest.mark.asyncio
async def test_delete_nonexistent_article_service(db_session: AsyncSession):
    assert await article_service.delete_article(db_session, 99999) is False


# ---------------------------------------------------------------------------
# comment_service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_comment_via_service(db_session: AsyncSession):
    user = await _create_user(db_session)
    article = await article_service.create_article(
        db_session,
        ArticleCreate(title="Commentable", content="C", is_published=True, user_id=user.id),
    )
    comment = await comment_service.add_comment(
        db_session, article["id"], CommentCreate(content="Great!", author_name="Reader")
    )
    assert comment is not None
    assert comment["content"] == "Great!"
    assert comment["author_name"] == "Reader"
    assert comment["article_id"] == article["id"]


@pytest.mark.asyncio
async def test_add_comment_nonexistent_article_service(db_session: AsyncSession):
    result = await comment_service.add_comment(
        db_session, 99999, CommentCreate(content="Ghost", author_name="Nobody")
    )
    assert result is None


# ---------------------------------------------------------------------------
# user_service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_users_via_service(db_session: AsyncSession):
    await _create_user(db_session, "u1", "u1@example.com")
    await _create_user(db_session, "u2", "u2@example.com")
    users = await user_service.get_users(db_session)
    assert len(users) == 2


@pytest.mark.asyncio
async def test_get_user_detail_via_service(db_session: AsyncSession):
    user = await _create_user(db_session)
    await article_service.create_article(
        db_session,
        ArticleCreate(title="User Article", content="C", is_published=True, user_id=user.id),
    )
    detail = await user_service.get_user(db_session, user.id)
    assert detail is not None
    assert detail["username"] == "svcuser"
    assert len(detail["articles"]) == 1


@pytest.mark.asyncio
async def test_get_user_not_found_service(db_session: AsyncSession):
    result = await user_service.get_user(db_session, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_create_user_via_service(db_session: AsyncSession):
    result = await user_service.create_user(
        db_session,
        UserCreate(username="created", email="created@example.com", display_name="Created", bio="Bio"),
    )
    assert result["username"] == "created"
    assert result["email"] == "created@example.com"


# ---------------------------------------------------------------------------
# slugify edge cases
# ---------------------------------------------------------------------------

def test_slugify_special_characters():
    assert article_service.slugify("Hello World!") == "hello-world"
    assert article_service.slugify("  Spaces  Everywhere  ") == "spaces-everywhere"
    assert article_service.slugify("UPPER-case---dashes") == "upper-case-dashes"
    assert article_service.slugify("a & b @ c") == "a--b--c" or "a-b-c" in article_service.slugify("a & b @ c")
