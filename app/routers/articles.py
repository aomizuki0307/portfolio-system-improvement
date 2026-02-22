from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import PaginationParams
from app.schemas import ArticleCreate, ArticleUpdate, ArticleDetail, CommentCreate, CommentResponse, PaginatedResponse
from app.services import article_service, comment_service

router = APIRouter(prefix="/api/v1/articles", tags=["articles"])

@router.get("", response_model=PaginatedResponse)
async def list_articles(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    return await article_service.get_articles(
        db, pagination.page, pagination.page_size, pagination.sort_by, pagination.sort_order
    )

@router.get("/{article_id}")
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    article = await article_service.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.post("", status_code=201)
async def create_article(data: ArticleCreate, db: AsyncSession = Depends(get_db)):
    return await article_service.create_article(db, data)

@router.put("/{article_id}")
async def update_article(article_id: int, data: ArticleUpdate, db: AsyncSession = Depends(get_db)):
    article = await article_service.update_article(db, article_id, data)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.delete("/{article_id}", status_code=204)
async def delete_article(article_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await article_service.delete_article(db, article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found")

@router.post("/{article_id}/comments", status_code=201, response_model=CommentResponse)
async def add_comment(article_id: int, data: CommentCreate, db: AsyncSession = Depends(get_db)):
    comment = await comment_service.add_comment(db, article_id, data)
    if not comment:
        raise HTTPException(status_code=404, detail="Article not found")
    return comment
