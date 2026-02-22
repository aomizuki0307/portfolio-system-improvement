"""
User endpoint tests — covers creating users, listing users, fetching user
detail (with articles), and the metrics endpoint.

The metrics endpoint is tested here because it aggregates across users,
articles, and comments and is simpler to exercise once user and article
creation is established.
"""
import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Create user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_user(async_client: AsyncClient):
    """Creating a user with all fields returns 201 and all provided data."""
    resp = await async_client.post("/api/v1/users", json={
        "username": "newuser",
        "email": "newuser@example.com",
        "display_name": "New User",
        "bio": "I am new here",
    })
    assert resp.status_code == 201
    user = resp.json()
    assert user["username"] == "newuser"
    assert user["email"] == "newuser@example.com"
    assert user["display_name"] == "New User"
    assert user["bio"] == "I am new here"
    assert "id" in user
    assert "created_at" in user


@pytest.mark.asyncio
async def test_create_user_minimal_fields(async_client: AsyncClient):
    """Creating a user with only required fields (username + email) returns 201."""
    resp = await async_client.post("/api/v1/users", json={
        "username": "minimal",
        "email": "minimal@example.com",
    })
    assert resp.status_code == 201
    user = resp.json()
    assert user["username"] == "minimal"
    assert user["display_name"] is None
    assert user["bio"] is None


@pytest.mark.asyncio
async def test_create_user_missing_username(async_client: AsyncClient):
    """Omitting the required 'username' field returns 422 Unprocessable Entity."""
    resp = await async_client.post("/api/v1/users", json={
        "email": "nousername@example.com",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_user_missing_email(async_client: AsyncClient):
    """Omitting the required 'email' field returns 422 Unprocessable Entity."""
    resp = await async_client.post("/api/v1/users", json={
        "username": "noemail",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_users_empty(async_client: AsyncClient):
    """Listing users with no data returns an empty list."""
    resp = await async_client.get("/api/v1/users")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_users(async_client: AsyncClient):
    """All created users appear in the list endpoint."""
    for i in range(2):
        await async_client.post("/api/v1/users", json={
            "username": f"listuser{i}",
            "email": f"listuser{i}@example.com",
        })

    resp = await async_client.get("/api/v1/users")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 2


@pytest.mark.asyncio
async def test_list_users_count_increases_with_each_creation(async_client: AsyncClient):
    """The user count in the list response increments correctly with each creation."""
    for i in range(3):
        await async_client.post("/api/v1/users", json={
            "username": f"counter{i}",
            "email": f"counter{i}@example.com",
        })
        resp = await async_client.get("/api/v1/users")
        assert len(resp.json()) == i + 1


# ---------------------------------------------------------------------------
# Get user detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_detail(async_client: AsyncClient):
    """User detail endpoint returns user data and includes the user's articles."""
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "detailuser",
        "email": "detailuser@example.com",
    })
    user_id = user_resp.json()["id"]

    await async_client.post("/api/v1/articles", json={
        "title": "User's Article",
        "content": "Content by user",
        "is_published": True,
        "user_id": user_id,
    })

    resp = await async_client.get(f"/api/v1/users/{user_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["username"] == "detailuser"
    assert len(detail["articles"]) == 1
    assert detail["articles"][0]["title"] == "User's Article"


@pytest.mark.asyncio
async def test_get_user_detail_no_articles(async_client: AsyncClient):
    """User detail for a user with no articles returns an empty articles list."""
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "noarticles",
        "email": "noarticles@example.com",
    })
    user_id = user_resp.json()["id"]

    resp = await async_client.get(f"/api/v1/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["articles"] == []


@pytest.mark.asyncio
async def test_get_user_detail_multiple_articles(async_client: AsyncClient):
    """User detail lists all articles belonging to that user."""
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "prolific",
        "email": "prolific@example.com",
    })
    user_id = user_resp.json()["id"]

    for i in range(4):
        await async_client.post("/api/v1/articles", json={
            "title": f"Prolific Article {i}",
            "content": f"Content {i}",
            "is_published": True,
            "user_id": user_id,
        })

    resp = await async_client.get(f"/api/v1/users/{user_id}")
    assert resp.status_code == 200
    assert len(resp.json()["articles"]) == 4


# ---------------------------------------------------------------------------
# User not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_not_found(async_client: AsyncClient):
    """Fetching a non-existent user ID returns 404."""
    resp = await async_client.get("/api/v1/users/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metrics_endpoint_empty(async_client: AsyncClient):
    """Metrics endpoint returns zero counts on an empty database."""
    resp = await async_client.get("/api/v1/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_articles"] == 0
    assert data["total_comments"] == 0
    assert data["total_users"] == 0
    assert data["avg_comments_per_article"] == 0.0
    assert "cache_info" in data


@pytest.mark.asyncio
async def test_metrics_endpoint(async_client: AsyncClient):
    """Metrics endpoint returns accurate counts for created entities."""
    # Create a user.
    user_resp = await async_client.post("/api/v1/users", json={
        "username": "metricuser",
        "email": "metricuser@example.com",
    })
    user_id = user_resp.json()["id"]

    # Create two articles.
    article_ids = []
    for i in range(2):
        art_resp = await async_client.post("/api/v1/articles", json={
            "title": f"Metric Article {i}",
            "content": f"Content {i}",
            "is_published": True,
            "user_id": user_id,
        })
        article_ids.append(art_resp.json()["id"])

    # Add 3 comments to the first article.
    for i in range(3):
        await async_client.post(f"/api/v1/articles/{article_ids[0]}/comments", json={
            "content": f"Metric comment {i}",
            "author_name": "Reader",
        })

    resp = await async_client.get("/api/v1/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_articles"] == 2
    assert data["total_comments"] == 3
    assert data["total_users"] == 1
    # avg = 3 comments / 2 articles = 1.5
    assert data["avg_comments_per_article"] == 1.5
    assert "cache_info" in data


@pytest.mark.asyncio
async def test_metrics_cache_info_structure(async_client: AsyncClient):
    """The cache_info field in metrics contains hits, misses, and hit_rate."""
    resp = await async_client.get("/api/v1/metrics")
    assert resp.status_code == 200
    cache_info = resp.json()["cache_info"]
    assert "hits" in cache_info
    assert "misses" in cache_info
    assert "hit_rate" in cache_info
