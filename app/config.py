from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://bloguser:blogpass@localhost:5433/blogdb"
    REDIS_URL: str = "redis://localhost:6380/0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"

    # Cache TTLs
    CACHE_TTL_LIST: int = 60
    CACHE_TTL_DETAIL: int = 300

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
