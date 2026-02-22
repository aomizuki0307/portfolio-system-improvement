from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ---------------------------------------------------------------------------
# Association table: Article <-> Tag (many-to-many)
# ---------------------------------------------------------------------------
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships — lazy="noload" enforces explicit eager loading in services
    articles: Mapped[List["Article"]] = relationship(
        "Article", back_populates="author", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------
class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Relationships
    articles: Mapped[List["Article"]] = relationship(
        "Article", secondary=article_tags, back_populates="tags", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------
class Article(Base):
    __tablename__ = "articles"

    __table_args__ = (
        # User's articles sorted by date (e.g. profile page, author feed)
        Index("ix_articles_user_id_created_at", "user_id", "created_at"),
        # Published articles feed (homepage, RSS)
        Index("ix_articles_is_published_created_at", "is_published", "created_at"),
        # Popular articles ranking
        Index("ix_articles_view_count", "view_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(350), unique=True, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Foreign key
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships — all lazy="noload" to prevent N+1; use selectinload/joinedload in services
    author: Mapped["User"] = relationship("User", back_populates="articles", lazy="noload")
    comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="article", lazy="noload"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=article_tags, back_populates="articles", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------
class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Foreign key
    article_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    article: Mapped["Article"] = relationship("Article", back_populates="comments", lazy="noload")
