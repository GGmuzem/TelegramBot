from pathlib import Path
from functools import lru_cache
from pydantic import BaseSettings, Field, AnyUrl, validator

class Settings(BaseSettings):
    # ——— Общие ———
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")

    # ——— Telegram ———
    BOT_TOKEN: str
    BOT_WEBHOOK_URL: AnyUrl | None = None
    WEBHOOK_SECRET: str

    # ——— DB & Redis ———
    DATABASE_URL: AnyUrl
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    REDIS_URL: AnyUrl

    # ——— Payments ———
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    YOOKASSA_WEBHOOK_SECRET: str | None = None
    CLOUDPAYMENTS_PUBLIC_ID: str | None = None
    CLOUDPAYMENTS_SECRET_KEY: str | None = None
    CLOUDPAYMENTS_WEBHOOK_SECRET: str | None = None

    # ——— Storage ———
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MODEL_CACHE_DIR: Path = Path("./models")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# Пакеты для продажи
PACKAGES = {
    "once":    {"name": "Разовая",  "price": 49,  "images": 1,  "quality": "standard"},
    "basic":   {"name": "Базовый",  "price": 299, "images": 10, "quality": "standard"},
    "premium": {"name": "Премиум",  "price": 599, "images": 25, "quality": "high"},
    "pro":     {"name": "Профи",    "price": 1299,"images": 60, "quality": "ultra"},
}
