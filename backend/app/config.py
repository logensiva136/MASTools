from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "mastools"
    postgres_password: str = "change-me"
    postgres_db: str = "mastools"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    database_url: str | None = None

    redis_host: str = "redis"
    redis_port: int = 6379
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 500
    catalog_version: str = "MASVS-v2.1"
    catalog_dir: str = "/data/catalog"

    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or f"redis://{self.redis_host}:{self.redis_port}/1"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
