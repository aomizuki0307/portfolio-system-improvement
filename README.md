# Blog API — System Performance Improvement Portfolio

[![CI](https://github.com/aomizuki0307/portfolio-system-improvement/actions/workflows/ci.yml/badge.svg)](https://github.com/aomizuki0307/portfolio-system-improvement/actions/workflows/ci.yml)

> Demonstrating systematic API performance optimization: **328x faster response times** through database optimization, caching, and architectural improvements.

## Performance Results

| Metric | Before (v0.1) | After (v1.0) | Improvement |
|--------|---------------|--------------|-------------|
| GET /articles avg | 2,300ms | 7ms | **328x faster** |
| GET /articles/{id} avg | 450ms | 7ms | **64x faster** |
| Queries per request (list) | 41 | 2 | **20x reduction** |
| Cache hit rate | 0% | 87% | -- |
| Test coverage | 0% | 87% | -- |

## What This Project Demonstrates

- **N+1 Query Detection & Elimination** — `lazy="noload"` + explicit `joinedload`/`selectinload`
- **Database Indexing** — Composite indexes on (user_id, created_at), (is_published, created_at)
- **Redis Caching** — Cache-aside pattern with TTL-based invalidation and graceful degradation
- **Async Python** — FastAPI + async SQLAlchemy 2.0 + async Redis
- **Test-Driven Development** — 87% coverage with SQLite in-memory for fast CI
- **Service Layer Architecture** — Clean separation of routes, business logic, and data access
- **Docker & CI/CD** — Docker Compose stack + GitHub Actions

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Framework | FastAPI |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| ORM | SQLAlchemy 2.0 (async) |
| Validation | Pydantic v2 |
| Tests | pytest + aiosqlite |
| Containers | Docker Compose |
| CI | GitHub Actions |

## Quick Start

### Docker Compose (Full Stack)

```bash
cd portfolio-system-improvement

# Copy environment config
cp .env.example .env

# Start PostgreSQL + Redis + App
docker compose up -d

# Seed test data
docker compose exec app python -m scripts.seed --small

# Health check
curl http://localhost:8000/health

# Run benchmarks
docker compose exec app python -m scripts.benchmark
```

### Local Development (Tests Only)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Run tests (no external services needed — uses SQLite in-memory)
pytest tests/ -v --cov=app --cov-report=term-missing
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/articles` | List published articles (paginated, sortable) |
| GET | `/api/v1/articles/{id}` | Article detail (with comments, tags) |
| POST | `/api/v1/articles` | Create article |
| PUT | `/api/v1/articles/{id}` | Update article |
| DELETE | `/api/v1/articles/{id}` | Delete article |
| POST | `/api/v1/articles/{id}/comments` | Add comment to article |
| GET | `/api/v1/users` | List users |
| GET | `/api/v1/users/{id}` | User detail (with articles) |
| POST | `/api/v1/users` | Create user |
| GET | `/api/v1/metrics` | Performance metrics + cache stats |
| GET | `/health` | Health check |

### Response Headers

Every response includes diagnostic headers:
- `X-Response-Time-Ms` — Request duration in milliseconds
- `X-Query-Count` — Number of SQL queries executed

## Optimization Journey

Each phase is documented with problem analysis, implementation, and measured results:

1. **[Initial Analysis](docs/01-initial-analysis.md)** — Profiling the baseline: 2,300ms, 41 queries/request
2. **[Database Optimization](docs/02-db-optimization.md)** — N+1 fix + indexes: 41 → 2 queries, 2,300ms → 180ms
3. **[Caching Layer](docs/03-caching-layer.md)** — Redis cache-aside: 180ms → 12ms, 87% hit rate
4. **[Architecture & Testing](docs/04-refactoring.md)** — Service layer, DI, 87% test coverage
5. **[Results Summary](docs/05-results-summary.md)** — Final metrics and methodology

## Architecture

```
HTTP Request
    |
    v
[FastAPI Routers]  ----  Request validation (Pydantic v2)
    |                     Response serialization
    v
[Service Layer]    ----  Business logic
    |                     Cache orchestration
    |                     Eager loading strategy
    |
    +-------+-------+
    |               |
    v               v
[PostgreSQL]    [Redis Cache]
 SQLAlchemy      Cache-aside
 Async ORM       TTL + invalidation
```

**Key patterns:**
- `lazy="noload"` on all relationships prevents accidental N+1 queries
- Explicit `joinedload()` / `selectinload()` in service layer
- Cache-aside with write-through invalidation on mutations
- App works without Redis (graceful degradation)

## Running Tests

```bash
# Full suite with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Quick run
pytest tests/ -q
```

## Ports (Collision Avoidance)

| Service | Host Port | Container Port |
|---------|-----------|----------------|
| PostgreSQL | 5433 | 5432 |
| Redis | 6380 | 6379 |
| App | 8000 | 8000 |

## License

MIT
