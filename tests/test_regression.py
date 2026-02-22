"""
Regression tests for issues found during code review.

1. Unique constraint violations must return 409 (not 500)
2. view_count must increment on every access (including cache hits)
3. X-Query-Count header must report actual query count (not always 0)
4. CORS must not set allow_credentials=true with allow_origins=*
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import article_service
from app.schemas import ArticleCreate


# ---------------------------------------------------------------------------
# 1. Unique constraint violations -> 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_user_returns_409(async_client: AsyncClient):
    """Creating a user with an existing username returns 409, not 500."""
    payload = {"username": "dup_user", "email": "dup1@example.com"}
    resp1 = await async_client.post("/api/v1/users", json=payload)
    assert resp1.status_code == 201

    payload2 = {"username": "dup_user", "email": "dup2@example.com"}
    resp2 = await async_client.post("/api/v1/users", json=payload2)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_email_returns_409(async_client: AsyncClient):
    """Creating a user with an existing email returns 409, not 500."""
    await async_client.post("/api/v1/users", json={
        "username": "emailuser1", "email": "same@example.com",
    })
    resp = await async_client.post("/api/v1/users", json={
        "username": "emailuser2", "email": "same@example.com",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_article_slug_collision_handled(async_client: AsyncClient):
    """Updating a title to match another article's slug doesn't cause 500."""
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "slug_col", "email": "slug_col@example.com",
    })
    user_id = user_resp.json()["id"]

    # Create two articles with different titles.
    resp1 = await async_client.post("/api/v1/articles", json={
        "title": "First Article",
        "content": "Content A",
        "is_published": True,
        "user_id": user_id,
    })
    assert resp1.status_code == 201

    resp2 = await async_client.post("/api/v1/articles", json={
        "title": "Second Article",
        "content": "Content B",
        "is_published": True,
        "user_id": user_id,
    })
    article2_id = resp2.json()["id"]

    # Update article 2's title to match article 1's slug.
    resp = await async_client.put(f"/api/v1/articles/{article2_id}", json={
        "title": "First Article",
    })
    # Must succeed (with timestamp-suffixed slug) or return 409 -- not 500.
    assert resp.status_code in (200, 409)
    if resp.status_code == 200:
        # Slug must differ from "first-article" (collision avoidance).
        assert resp.json()["slug"] != "first-article"


# ---------------------------------------------------------------------------
# 2. view_count increments on every access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_view_count_increments_on_repeated_access(db_session: AsyncSession):
    """view_count must increase on each get_article call."""
    user = await _create_user(db_session)
    created = await article_service.create_article(
        db_session,
        ArticleCreate(
            title="View Counter",
            content="Content",
            is_published=True,
            user_id=user.id,
        ),
    )
    article_id = created["id"]

    detail1 = await article_service.get_article(db_session, article_id)
    assert detail1 is not None
    count1 = detail1["view_count"]

    detail2 = await article_service.get_article(db_session, article_id)
    assert detail2 is not None
    count2 = detail2["view_count"]

    assert count2 == count1 + 1, (
        f"view_count did not increment: {count1} -> {count2}"
    )


@pytest.mark.asyncio
async def test_view_count_increments_via_http(async_client: AsyncClient):
    """view_count must increase on repeated HTTP GET calls."""
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "viewer", "email": "viewer@example.com",
    })
    user_id = user_resp.json()["id"]

    art_resp = await async_client.post("/api/v1/articles", json={
        "title": "HTTP View Counter",
        "content": "Content",
        "is_published": True,
        "user_id": user_id,
    })
    article_id = art_resp.json()["id"]

    resp1 = await async_client.get(f"/api/v1/articles/{article_id}")
    count1 = resp1.json()["view_count"]

    resp2 = await async_client.get(f"/api/v1/articles/{article_id}")
    count2 = resp2.json()["view_count"]

    assert count2 == count1 + 1


# ---------------------------------------------------------------------------
# 3. X-Query-Count reports actual query count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_count_header_exact_for_article_list(async_client: AsyncClient):
    """
    X-Query-Count must reflect ALL SQL statements including selectinload
    internals.  Article list issues: COUNT + SELECT(joinedload author) +
    selectinload(tags) = 3 queries.
    """
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "qctest", "email": "qctest@example.com",
    })
    user_id = user_resp.json()["id"]
    await async_client.post("/api/v1/articles", json={
        "title": "QC Article",
        "content": "Content",
        "is_published": True,
        "user_id": user_id,
    })

    resp = await async_client.get("/api/v1/articles")
    assert resp.status_code == 200
    count = int(resp.headers["x-query-count"])
    assert count == 3, f"Expected exactly 3 queries for article list, got {count}"


@pytest.mark.asyncio
async def test_query_count_header_exact_for_article_detail(async_client: AsyncClient):
    """
    X-Query-Count for article detail must count: existence check +
    UPDATE view_count + SELECT(joinedload author) + selectinload(tags) +
    selectinload(comments) = 5 queries.
    """
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "qcdetail", "email": "qcdetail@example.com",
    })
    user_id = user_resp.json()["id"]
    art_resp = await async_client.post("/api/v1/articles", json={
        "title": "QC Detail Article",
        "content": "Content",
        "is_published": True,
        "user_id": user_id,
    })
    article_id = art_resp.json()["id"]

    resp = await async_client.get(f"/api/v1/articles/{article_id}")
    assert resp.status_code == 200
    count = int(resp.headers["x-query-count"])
    assert count == 5, f"Expected exactly 5 queries for article detail, got {count}"


# ---------------------------------------------------------------------------
# 4. CORS headers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cors_no_credentials_with_wildcard_origin(async_client: AsyncClient):
    """
    When allow_origins=["*"], the response must NOT include
    Access-Control-Allow-Credentials: true, per the CORS specification.
    """
    resp = await async_client.options(
        "/api/v1/articles",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    cred_header = resp.headers.get("access-control-allow-credentials", "").lower()
    assert cred_header != "true", (
        "CORS must not combine allow_origins=* with allow_credentials=true"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(db_session: AsyncSession, username="reguser", email="reg@example.com"):
    from app.models import User
    user = User(username=username, email=email, display_name="Regression User")
    db_session.add(user)
    await db_session.flush()
    return user
