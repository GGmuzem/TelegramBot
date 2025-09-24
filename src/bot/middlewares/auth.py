"""
Middleware для аутентификации пользователей
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from src.database.crud import UserCRUD

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware для автоматической регистрации и авторизации пользователей"""
    
    def __init__(self):
        self.user_crud = UserCRUD()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основная логика middleware"""
        
        # Получаем пользователя из события
        telegram_user = None
        if isinstance(event, (Message, CallbackQuery)):
            telegram_user = event.from_user
        
        if not telegram_user:
            return await handler(event, data)
        
        try:
            # Получаем или создаем пользователя в базе данных
            user = await self.user_crud.get_or_create_user(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name or "Unknown",
                last_name=telegram_user.last_name,
                language_code=telegram_user.language_code or "ru"
            )
            
            if not user:
                logger.error(f"Не удалось создать/получить пользователя {telegram_user.id}")
                return
            
            # Обновляем последнюю активность
            await self.user_crud.update_last_activity(user.telegram_id)
            
            # Добавляем пользователя в контекст
            data['user'] = {
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.full_name,
                'balance': user.balance,
                'subscription_type': user.subscription_type,
                'total_generations': user.total_generations,
                'total_spent': float(user.total_spent or 0),
                'created_at': user.created_at,
                'last_activity': user.last_activity,
                'is_admin': user.is_admin,
                'status': user.status
            }
            
            # Логируем активность пользователя
            if isinstance(event, Message):
                logger.info(
                    f"Пользователь {user.telegram_id} ({user.username or user.full_name}) "
                    f"отправил сообщение: {event.text[:50] if event.text else 'Медиа'}"
                )
            elif isinstance(event, CallbackQuery):
                logger.info(
                    f"Пользователь {user.telegram_id} ({user.username or user.full_name}) "
                    f"нажал кнопку: {event.data}"
                )
            
            return await handler(event, data)
            
        except Exception as e:
            logger.error(f"Ошибка в AuthMiddleware для пользователя {telegram_user.id}: {e}")
            # Продолжаем выполнение даже при ошибке авторизации
            return await handler(event, data)