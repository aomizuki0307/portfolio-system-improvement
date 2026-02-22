from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


# --- Tag ---

class TagBase(BaseModel):
    name: str = Field(max_length=50)


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- User ---

class UserBase(BaseModel):
    username: str = Field(max_length=50)
    email: str = Field(max_length=255)
    display_name: str | None = None
    bio: str | None = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserDetail(UserResponse):
    articles: list["ArticleResponse"] = []


# --- Comment ---

class CommentBase(BaseModel):
    content: str
    author_name: str = Field(max_length=100)


class CommentCreate(CommentBase):
    pass


class CommentResponse(CommentBase):
    id: int
    article_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Article ---

class ArticleBase(BaseModel):
    title: str = Field(max_length=200)
    content: str
    summary: str | None = Field(None, max_length=500)
    is_published: bool = False
    tags: list[str] = []  # tag names for create/update


class ArticleCreate(ArticleBase):
    user_id: int


class ArticleUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    content: str | None = None
    summary: str | None = Field(None, max_length=500)
    is_published: bool | None = None
    tags: list[str] | None = None


class ArticleResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: str | None
    view_count: int
    is_published: bool
    published_at: datetime | None
    created_at: datetime
    user_id: int
    author: UserResponse | None = None
    tags: list[TagResponse] = []
    model_config = ConfigDict(from_attributes=True)


class ArticleDetail(ArticleResponse):
    content: str
    comments: list[CommentResponse] = []


# --- Pagination ---

class PaginatedResponse(BaseModel):
    items: list  # Will be typed in router
    total: int
    page: int
    page_size: int
    pages: int


# --- Metrics ---

class MetricsResponse(BaseModel):
    total_articles: int
    total_comments: int
    total_users: int
    avg_comments_per_article: float
    cache_info: dict = {}


# Required for forward-reference resolution (UserDetail.articles)
UserDetail.model_rebuild()
