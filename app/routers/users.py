from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import UserCreate, UserResponse, UserDetail
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.get("", response_model=list[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    return await user_service.get_users(db)

@router.get("/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("", status_code=201, response_model=UserResponse)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await user_service.create_user(db, data)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A user with this username or email already exists",
        )
