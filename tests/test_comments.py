"""
Comment endpoint tests — covers adding comments, validation, and verifying
that article detail responses include comment data.

Comments are append-only in this API (no edit/delete endpoints), so the
test surface is focused on creation and read-through verification.
"""
import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user_and_article(client: AsyncClient, suffix: str) -> tuple[int, int]:
    """
    Create a user and a published article, returning (user_id, article_id).

    Using a unique suffix per test avoids unique-constraint conflicts when
    multiple tests run against the same in-memory database within one session.
    """
    user_resp = await client.post("/api/v1/users", json={
        "username": f"user_{suffix}",
        "email": f"user_{suffix}@example.com",
    })
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    article_resp = await client.post("/api/v1/articles", json={
        "title": f"Article for {suffix}",
        "content": "Article content",
        "is_published": True,
        "user_id": user_id,
    })
    assert article_resp.status_code == 201
    article_id = article_resp.json()["id"]

    return user_id, article_id


# ---------------------------------------------------------------------------
# Add comment — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_comment(async_client: AsyncClient):
    """Posting a comment returns 201 with the correct fields."""
    _, article_id = await _create_user_and_article(async_client, "add_comment")

    resp = await async_client.post(
        f"/api/v1/articles/{article_id}/comments",
        json={"content": "Great article!", "author_name": "Reader"},
    )
    assert resp.status_code == 201
    comment = resp.json()
    assert comment["content"] == "Great article!"
    assert comment["author_name"] == "Reader"
    assert comment["article_id"] == article_id
    assert "id" in comment
    assert "created_at" in comment


@pytest.mark.asyncio
async def test_add_multiple_comments(async_client: AsyncClient):
    """Multiple comments can be posted to the same article."""
    _, article_id = await _create_user_and_article(async_client, "multi_comment")

    for i in range(3):
        resp = await async_client.post(
            f"/api/v1/articles/{article_id}/comments",
            json={"content": f"Comment {i}", "author_name": f"Reader {i}"},
        )
        assert resp.status_code == 201

    # Verify via the article detail endpoint.
    detail_resp = await async_client.get(f"/api/v1/articles/{article_id}")
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["comments"]) == 3


# ---------------------------------------------------------------------------
# Add comment — error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comment_on_nonexistent_article(async_client: AsyncClient):
    """Posting a comment to a non-existent article ID returns 404."""
    resp = await async_client.post(
        "/api/v1/articles/99999/comments",
        json={"content": "Ghost comment", "author_name": "Ghost"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_comment_missing_content_field(async_client: AsyncClient):
    """Omitting the required 'content' field returns 422 Unprocessable Entity."""
    _, article_id = await _create_user_and_article(async_client, "missing_content")

    resp = await async_client.post(
        f"/api/v1/articles/{article_id}/comments",
        json={"author_name": "Incomplete Reader"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_comment_missing_author_name_field(async_client: AsyncClient):
    """Omitting the required 'author_name' field returns 422 Unprocessable Entity."""
    _, article_id = await _create_user_and_article(async_client, "missing_author")

    resp = await async_client.post(
        f"/api/v1/articles/{article_id}/comments",
        json={"content": "Anonymous content"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Article detail includes comments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_article_detail_includes_comments(async_client: AsyncClient):
    """Article detail response includes all posted comments with correct data."""
    _, article_id = await _create_user_and_article(async_client, "detail_comments")

    for i in range(3):
        await async_client.post(
            f"/api/v1/articles/{article_id}/comments",
            json={"content": f"Comment {i}", "author_name": f"Reader {i}"},
        )

    resp = await async_client.get(f"/api/v1/articles/{article_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["comments"]) == 3

    # Verify each comment has the required fields.
    for comment in detail["comments"]:
        assert "id" in comment
        assert "content" in comment
        assert "author_name" in comment
        assert "created_at" in comment
        assert comment["article_id"] == article_id


@pytest.mark.asyncio
async def test_article_detail_empty_comments_on_new_article(async_client: AsyncClient):
    """A freshly created article has an empty comments list in the detail response."""
    _, article_id = await _create_user_and_article(async_client, "no_comments")

    resp = await async_client.get(f"/api/v1/articles/{article_id}")
    assert resp.status_code == 200
    assert resp.json()["comments"] == []


@pytest.mark.asyncio
async def test_comment_data_preserved_in_detail(async_client: AsyncClient):
    """Comment content and author name are preserved exactly as submitted."""
    _, article_id = await _create_user_and_article(async_client, "preserved_data")

    await async_client.post(
        f"/api/v1/articles/{article_id}/comments",
        json={"content": "Exact content here", "author_name": "Precise Author"},
    )

    resp = await async_client.get(f"/api/v1/articles/{article_id}")
    comment = resp.json()["comments"][0]
    assert comment["content"] == "Exact content here"
    assert comment["author_name"] == "Precise Author"
