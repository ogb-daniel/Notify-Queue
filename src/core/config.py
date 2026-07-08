from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "NotifyQueue"

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    CORS_ORIGINS: list[str] = ["*"]

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_LOCK_TIMEOUT_SECONDS: int = 300
    REDIS_LOCK_PREFIX: str = "notify:claim:"
    REDIS_RATE_LIMIT_PREFIX: str = "notify:rate:"

    WORKER_POLL_INTERVAL_SECONDS: float = 0.5
    WORKER_BATCH_SIZE: int = 10

    FAILURE_RATE: float = 0.2
    MAX_RETRIES: int = 5
    BACKOFF_BASE_SECONDS: float = 2.0
    BACKOFF_MAX_SECONDS: float = 3600.0

    RATE_LIMIT_PER_RECIPIENT_PER_HOUR: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 3600

    WEBHOOK_TIMEOUT_SECONDS: float = 5.0

    @property
    def DB_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self):
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()