from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://terraflora:terraflora@localhost:5432/terraflora"
    REDIS_URL: str = "redis://localhost:6379"
    PLANTNET_API_KEY: str = ""
    CESIUM_ION_TOKEN: str = ""
    JWT_SECRET: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = "terraflora-uploads"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    PLANTNET_AUTO_APPROVE_THRESHOLD: float = 0.85
    PLANTNET_REVIEW_THRESHOLD: float = 0.50

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
