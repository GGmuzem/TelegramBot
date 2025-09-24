"""
Middleware для ограничения частоты запросов (Rate Limiting)
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from src.shared.redis_client import redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов пользователей"""
    
    def __init__(self):
        # Лимиты по типам действий (requests per minute)
        self.limits = {
            'message': 30,      # Обычные сообщения
            'callback': 60,     # Нажатия кнопок
            'generation': 5,    # Запросы на генерацию
            'payment': 10,      # Платежные запросы
            'admin': 100        # Админские действия
        }
        
        # Временные окна (в секундах)
        self.windows = {
            'message': 60,      # 1 минута
            'callback': 60,     # 1 минута  
            'generation': 300,  # 5 минут
            'payment': 3600,    # 1 час
            'admin': 60         # 1 минута
        }
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основная логика middleware"""
        
        # Получаем информацию о пользователе
        user_data = data.get('user')
        if not user_data:
            return await handler(event, data)
        
        user_id = user_data['telegram_id']
        
        # Админы не ограничиваются
        if user_data.get('is_admin', False):
            return await handler(event, data)
        
        try:
            # Определяем тип действия
            action_type = self._get_action_type(event, data)
            
            # Проверяем лимиты
            if not await self._check_rate_limit(user_id, action_type):
                await self._handle_rate_limit_exceeded(event, action_type)
                return
            
            # Инкрементируем счетчик
            await self._increment_counter(user_id, action_type)
            
            return await handler(event, data)
            
        except Exception as e:
            logger.error(f"Ошибка в RateLimitMiddleware для пользователя {user_id}: {e}")
            # В случае ошибки пропускаем проверку
            return await handler(event, data)
    
    def _get_action_type(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        """Определение типа действия для rate limiting"""
        
        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            
            # Платежные действия
            if any(keyword in callback_data for keyword in ['buy', 'payment', 'pay']):
                return 'payment'
            
            # Генерация изображений
            if any(keyword in callback_data for keyword in ['generate', 'style', 'quality']):
                return 'generation'
            
            # Админские действия
            if callback_data.startswith('admin_'):
                return 'admin'
            
            return 'callback'
        
        elif isinstance(event, Message):
            # Определяем тип по содержимому сообщения
            if event.text:
                text = event.text.lower()
                
                # Команды генерации
                if any(keyword in text for keyword in ['/generate', 'генерир', 'создай', 'нарисуй']):
                    return 'generation'
                
                # Админские команды
                if text.startswith('/admin') or 'админ' in text:
                    return 'admin'
            
            return 'message'
        
        return 'message'
    
    async def _check_rate_limit(self, user_id: int, action_type: str) -> bool:
        """Проверка лимита запросов"""
        try:
            limit = self.limits.get(action_type, 30)
            window = self.windows.get(action_type, 60)
            
            # Проверяем текущий счетчик
            current_count = await redis_client.get(f"rate_limit:{user_id}:{action_type}")
            
            if current_count is None:
                return True
            
            if int(current_count) >= limit:
                logger.warning(
                    f"Rate limit exceeded: user {user_id}, action {action_type}, "
                    f"count {current_count}, limit {limit}"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки rate limit: {e}")
            return True  # В случае ошибки разрешаем запрос
    
    async def _increment_counter(self, user_id: int, action_type: str):
        """Инкремент счетчика запросов"""
        try:
            key = f"rate_limit:{user_id}:{action_type}"
            window = self.windows.get(action_type, 60)
            
            current = await redis_client.increment_counter(key)
            
            # Устанавливаем TTL только для первого запроса
            if current == 1:
                await redis_client.expire(key, window)
            
        except Exception as e:
            logger.error(f"Ошибка инкремента счетчика rate limit: {e}")
    
    async def _handle_rate_limit_exceeded(self, event: TelegramObject, action_type: str):
        """Обработка превышения лимита"""
        try:
            # Сообщения об ограничениях
            messages = {
                'message': (
                    "⚠️ Слишком много сообщений!\n\n"
                    "Пожалуйста, подождите немного перед отправкой следующего сообщения."
                ),
                'callback': (
                    "⚠️ Слишком быстро!\n\n"
                    "Пожалуйста, не нажимайте кнопки так часто."
                ),
                'generation': (
                    "⚠️ Лимит генераций превышен!\n\n"
                    "Максимум 5 запросов на генерацию за 5 минут.\n"
                    "Попробуйте позже или купите премиум для увеличения лимитов."
                ),
                'payment': (
                    "⚠️ Слишком много попыток оплаты!\n\n"
                    "Максимум 10 платежных запросов в час.\n"
                    "Если возникли проблемы, обратитесь в поддержку."
                ),
                'admin': (
                    "⚠️ Превышен лимит админских действий!\n\n"
                    "Подождите минуту перед следующей командой."
                )
            }
            
            message_text = messages.get(action_type, messages['message'])
            
            if isinstance(event, Message):
                await event.answer(message_text)
            elif isinstance(event, CallbackQuery):
                await event.answer(message_text, show_alert=True)
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения о rate limit: {e}")
    
    async def get_user_limits_info(self, user_id: int) -> Dict[str, Dict[str, int]]:
        """Получение информации о текущих лимитах пользователя"""
        try:
            limits_info = {}
            
            for action_type in self.limits:
                key = f"rate_limit:{user_id}:{action_type}"
                current = await redis_client.get(key)
                ttl = await redis_client.ttl(key)
                
                limits_info[action_type] = {
                    'current': int(current) if current else 0,
                    'limit': self.limits[action_type],
                    'remaining_time': ttl if ttl > 0 else 0,
                    'remaining_requests': max(0, self.limits[action_type] - (int(current) if current else 0))
                }
            
            return limits_info
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о лимитах: {e}")
            return {}
    
    async def reset_user_limits(self, user_id: int, action_type: str = None):
        """Сброс лимитов пользователя (для админов)"""
        try:
            if action_type:
                key = f"rate_limit:{user_id}:{action_type}"
                await redis_client.delete(key)
            else:
                # Сбрасываем все лимиты
                for action in self.limits:
                    key = f"rate_limit:{user_id}:{action}"
                    await redis_client.delete(key)
            
            logger.info(f"Сброшены лимиты для пользователя {user_id}, тип: {action_type or 'все'}")
            
        except Exception as e:
            logger.error(f"Ошибка сброса лимитов: {e}")


# Экземпляр middleware для использования в других модулях
rate_limit_middleware = RateLimitMiddleware()