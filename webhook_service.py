#!/usr/bin/env python3
"""
Точка входа для webhook сервиса
"""
import asyncio
import logging
from src.payment.webhook import app
from src.database.connection import init_database
from src.shared.redis_client import redis_client

async def startup():
    """Инициализация при запуске"""
    logging.basicConfig(level=logging.INFO)
    await init_database()
    await redis_client.connect()
    logging.info("🚀 Webhook service started")

if __name__ == "__main__":
    import uvicorn
    asyncio.run(startup())
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
