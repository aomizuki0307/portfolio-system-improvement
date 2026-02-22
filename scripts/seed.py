"""Database seeder for blog API benchmark testing."""
import asyncio
import argparse
import random
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from app.database import engine, async_session, Base
from app.models import User, Article, Comment, Tag

TAGS = ["python", "fastapi", "postgresql", "redis", "docker", "kubernetes",
        "react", "typescript", "aws", "devops", "testing", "performance",
        "security", "microservices", "graphql", "rest-api"]

async def seed(small: bool = False):
    num_users = 10 if small else 50
    num_articles = 100 if small else 10000
    num_comments_per_article = 2 if small else 5

    print(f"Seeding: {num_users} users, {num_articles} articles, ~{num_articles * num_comments_per_article} comments")
    start = time.perf_counter()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Create tags
        tags = []
        for name in TAGS:
            tag = Tag(name=name)
            session.add(tag)
            tags.append(tag)
        await session.flush()
        print(f"  Created {len(tags)} tags")

        # Create users
        users = []
        for i in range(num_users):
            user = User(
                username=f"user_{i:04d}",
                email=f"user_{i:04d}@example.com",
                display_name=f"User {i}",
                bio=f"I am test user number {i}. I write about technology."
            )
            session.add(user)
            users.append(user)
        await session.flush()
        print(f"  Created {len(users)} users")

        # Create articles in batches
        batch_size = 500
        total_comments = 0
        for batch_start in range(0, num_articles, batch_size):
            batch_end = min(batch_start + batch_size, num_articles)
            for i in range(batch_start, batch_end):
                days_ago = random.randint(0, 365)
                created = datetime.now(timezone.utc) - timedelta(days=days_ago)
                article = Article(
                    title=f"Article {i}: How to optimize {random.choice(TAGS)} applications",
                    slug=f"article-{i}-optimize-{random.choice(TAGS)}",
                    content=f"This is the full content of article {i}. " * 20,
                    summary=f"A guide to optimizing {random.choice(TAGS)} applications for production.",
                    view_count=random.randint(0, 10000),
                    is_published=random.random() > 0.1,  # 90% published
                    published_at=created if random.random() > 0.1 else None,
                    created_at=created,
                    user_id=random.choice(users).id,
                )
                # Add 1-4 random tags
                article_tags = random.sample(tags, k=random.randint(1, 4))
                article.tags.extend(article_tags)
                session.add(article)

            await session.flush()

            # Add comments for this batch of articles
            # Need to query articles to get IDs
            from sqlalchemy import select
            result = await session.execute(
                select(Article.id).where(Article.id > batch_start).limit(batch_size)
            )
            article_ids = [row[0] for row in result.all()]

            for article_id in article_ids:
                for _ in range(random.randint(1, num_comments_per_article)):
                    comment = Comment(
                        content=f"Great article! Very helpful for understanding the topic. Comment by {random.choice(users).username}.",
                        author_name=random.choice(users).username,
                        article_id=article_id,
                    )
                    session.add(comment)
                    total_comments += 1
            await session.flush()

            print(f"  Batch {batch_start}-{batch_end}: articles created")

        await session.commit()

    elapsed = time.perf_counter() - start
    print(f"\nSeeding complete in {elapsed:.1f}s")
    print(f"  Users: {num_users}")
    print(f"  Articles: {num_articles}")
    print(f"  Comments: ~{total_comments}")
    print(f"  Tags: {len(TAGS)}")


def main():
    parser = argparse.ArgumentParser(description="Seed the blog database")
    parser.add_argument("--small", action="store_true", help="Use small dataset (100 articles)")
    args = parser.parse_args()
    asyncio.run(seed(small=args.small))


if __name__ == "__main__":
    main()
