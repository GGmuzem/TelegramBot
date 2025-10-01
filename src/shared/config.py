from pathlib import Path
from functools import lru_cache
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    # ——— Общие ———
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "test_secret_key_for_development_only_change_in_production"

    # ——— Telegram ———
    BOT_TOKEN: str = "1234567890:TEST_TOKEN_FOR_TESTING"
    BOT_WEBHOOK_URL: str | None = None
    WEBHOOK_SECRET: str = "test_webhook_secret"

    # ——— DB & Redis ———
    DATABASE_URL: str = "postgresql+asyncpg://test:test@localhost/test_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    REDIS_URL: str = "redis://localhost:6379/0"

    # ——— Payments ———
    YOOKASSA_SHOP_ID: str = "test_shop_id"
    YOOKASSA_SECRET_KEY: str = "test_secret_key"
    YOOKASSA_WEBHOOK_SECRET: str | None = None
    CLOUDPAYMENTS_PUBLIC_ID: str | None = None
    CLOUDPAYMENTS_SECRET_KEY: str | None = None
    CLOUDPAYMENTS_WEBHOOK_SECRET: str | None = None

    # ——— Storage ———
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MODEL_CACHE_DIR: Path = Path("./models")

    # ——— Фискализация (АТОЛ) ———
    ATOL_LOGIN: str | None = None
    ATOL_PASSWORD: str | None = None
    ATOL_GROUP_CODE: str | None = None
    ATOL_COMPANY_INN: str | None = None
    ATOL_PAYMENT_ADDRESS: str | None = None

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# Пакеты тарифов
PACKAGES = {
    "once": {
        "name": "💎 Разовая",
        "price": 49,
        "images": 1,
        "quality": "standard",
        "size": "512x512",
        "description": "1 изображение стандартного качества",
        "validity_days": 0
    },
    "basic": {
        "name": "📦 Базовый",
        "price": 299,
        "images": 10,
        "quality": "standard",
        "size": "512x512",
        "description": "10 изображений стандартного качества",
        "validity_days": 30
    },
    "premium": {
        "name": "⭐ Премиум",
        "price": 599,
        "images": 25,
        "quality": "high",
        "size": "768x768",
        "description": "25 изображений высокого качества с приоритетом",
        "validity_days": 60
    },
    "pro": {
        "name": "🔥 Профи",
        "price": 1299,
        "images": 60,
        "quality": "ultra",
        "size": "1024x1024",
        "description": "60 изображений ультра качества без очереди",
        "validity_days": 90
    }
}
