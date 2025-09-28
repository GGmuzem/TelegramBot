"""
Главный файл Telegram бота - точка входа
"""
import asyncio
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.types import URLInputFile
import json

from redis.asyncio import Redis

# Импорты модулей бота
from src.bot.handlers import start, payment, generation, admin
from src.bot.middlewares.auth import AuthMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.shared.config import settings
from src.shared.redis_client import redis_client
from src.database.connection import init_database
from src.bot.webapp.routes import setup_webapp_routes

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Основной класс Telegram бота"""
    
    def __init__(self):
        # Создание бота
        self.bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Redis storage для FSM
        self.redis_storage = RedisStorage(
            redis=Redis.from_url(settings.REDIS_URL)
        )
        
        # Создание диспетчера
        self.dp = Dispatcher(storage=self.redis_storage)
        
        # Регистрация middleware
        self._setup_middlewares()
        
        # Регистрация handlers
        self._setup_handlers()

        # Фоновая задача для прослушивания результатов
        self.results_listener_task = None
    
    def _setup_middlewares(self):
        """Настройка middleware"""
        # Middleware авторизации
        self.dp.message.middleware(AuthMiddleware())
        self.dp.callback_query.middleware(AuthMiddleware())
        
        # Middleware ограничения частоты запросов
        self.dp.message.middleware(RateLimitMiddleware())
        self.dp.callback_query.middleware(RateLimitMiddleware())
    
    def _setup_handlers(self):
        """Регистрация обработчиков"""
        # Подключаем роутеры из handlers
        self.dp.include_routers(
            start.router,
            payment.router,
            generation.router,
            admin.router
        )
    
    async def results_listener(self):
        logger.info("Starting results listener...")
        while True:
            try:
                result_raw = await redis_client.redis.brpop("results_queue")
                if result_raw:
                    _, result_data_str = result_raw
                    result_data = json.loads(result_data_str)
                    
                    chat_id = result_data['chat_id']
                    prompt = result_data['prompt']
                    image_url = result_data['image_url']
                    
                    # Отправляем результат пользователю
                    image = URLInputFile(image_url)
                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=image,
                        caption=f"✅ Ваше изображение по запросу «{prompt[:50]}...» готово!"
                    )
            except Exception as e:
                logger.error(f"Error in results_listener: {e}")
            await asyncio.sleep(1)

    async def on_startup(self):
        """Инициализация при запуске"""
        try:
            # Инициализация Redis
            await redis_client.connect()
            
            # Инициализация базы данных
            await init_database()
            
            # Настройка webhook
            if settings.ENVIRONMENT == "production":
                webhook_url = f"{settings.BOT_WEBHOOK_URL}/webhook/telegram"
                await self.bot.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=True,
                    secret_token=settings.WEBHOOK_SECRET
                )
                logger.info(f"Webhook установлен: {webhook_url}")
            
            # Запускаем слушателя результатов
            self.results_listener_task = asyncio.create_task(self.results_listener())
            
            logger.info("🚀 Telegram Bot успешно запущен!")
            
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            raise
    
    async def on_shutdown(self):
        """Очистка при остановке"""
        try:
            await self.bot.delete_webhook()
            await self.dp.fsm.storage.close()
            await redis_client.disconnect()

            # Останавливаем слушателя
            if self.results_listener_task:
                self.results_listener_task.cancel()

            logger.info("🛑 Telegram Bot остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки бота: {e}")
    
    def create_app(self) -> web.Application:
        """Создание AIOHTTP приложения"""
        app = web.Application()
        
        # Настройка webhook handler для Telegram
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=self.dp,
            bot=self.bot,
            secret_token=settings.WEBHOOK_SECRET,
        )
        webhook_requests_handler.register(app, path="/webhook/telegram")
        
        # Health check endpoint
        async def health_check(request):
            return web.json_response({
                "status": "ok", 
                "timestamp": "2025-09-19T18:55:00Z"
            })
        
        app.router.add_get('/health', health_check)
        
        # Настройка webapp маршрутов для платежей
        setup_webapp_routes(app)
        
        # События приложения
        app.on_startup.append(lambda app: asyncio.create_task(self.on_startup()))
        app.on_cleanup.append(lambda app: asyncio.create_task(self.on_shutdown()))
        
        return app
    
    async def start_polling(self):
        """Запуск в режиме polling (для разработки)"""
        await self.on_startup()
        try:
            await self.dp.start_polling(self.bot)
        finally:
            await self.on_shutdown()


async def main():
    """Главная функция запуска"""
    bot_instance = TelegramBot()
    
    if settings.ENVIRONMENT == "development":
        # Режим polling для разработки
        await bot_instance.start_polling()
    else:
        # Режим webhook для production
        app = bot_instance.create_app()
        web.run_app(
            app,
            host="0.0.0.0",
            port=8000,
            access_log=logger
        )


if __name__ == "__main__":
    asyncio.run(main())