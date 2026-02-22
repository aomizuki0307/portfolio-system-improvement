from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.cache import cache
from app.middleware import TimingMiddleware
from app.routers import articles, users, metrics
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await cache.connect()
    except Exception:
        pass  # App works without Redis
    yield
    # Shutdown
    await cache.disconnect()

app = FastAPI(
    title="Blog API - Portfolio System Improvement",
    description="A blog API demonstrating systematic performance optimization",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(TimingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(articles.router)
app.include_router(users.router)
app.include_router(metrics.router)

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
