from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Article, Comment, User
from app.schemas import MetricsResponse
from app.cache import cache

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

@router.get("", response_model=MetricsResponse)
async def get_metrics(db: AsyncSession = Depends(get_db)):

    total_articles = (await db.execute(select(func.count()).select_from(Article))).scalar_one()

    total_comments = (await db.execute(select(func.count()).select_from(Comment))).scalar_one()

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()

    avg_comments = total_comments / total_articles if total_articles > 0 else 0

    return MetricsResponse(
        total_articles=total_articles,
        total_comments=total_comments,
        total_users=total_users,
        avg_comments_per_article=round(avg_comments, 2),
        cache_info=cache.stats,
    )
