"""
Упрощенный обработчик генерации AI изображений (без PyTorch зависимостей в боте)
"""
import json
import logging
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.bot.keyboards.main import get_back_keyboard, get_main_keyboard
from src.database.crud import UserCRUD
from src.shared.redis_client import redis_client

logger = logging.getLogger(__name__)
router = Router()

# CRUD сервисы
user_crud = UserCRUD()

# FSM состояния
class GenerationStates(StatesGroup):
    waiting_prompt = State()


@router.callback_query(F.data == "generate_image")
async def generate_image_handler(callback: CallbackQuery, user: dict, state: FSMContext):
    """Начало процесса генерации изображения"""
    try:
        # Проверяем баланс
        if user['balance'] <= 0:
            from src.bot.keyboards.payment import get_buy_packages_keyboard
            from src.payment.service import payment_service
            
            tariffs = await payment_service.get_tariffs()
            keyboard = get_buy_packages_keyboard(tariffs)
            
            await callback.message.edit_text(
                "❌ <b>Недостаточно средств на балансе!</b>\n\n"
                "Для генерации изображений необходимо пополнить баланс.\n"
                "Выберите подходящий тарифный план ниже.",
                reply_markup=keyboard
            )
            await callback.answer()
            return
        
        # Переводим в состояние ожидания промпта
        await state.set_state(GenerationStates.waiting_prompt)
        
        prompt_text = f"""🎨 <b>Генерация изображений</b>

💰 <b>Ваш баланс:</b> {user['balance']} изображений

📝 <b>Напишите описание изображения, которое хотите создать:</b>

🎯 <b>Примеры запросов:</b>
• "Красивый закат над морем в стиле импрессионизма"
• "Портрет девушки с голубыми глазами, фотореалистично"
• "Космический корабль в стиле киберпанк, неоновые цвета"
• "Милый котенок в стиле аниме"

✨ <b>Советы:</b>
• Используйте детальные описания
• Указывайте стиль и настроение
• Можете писать на русском языке
• Чем подробнее описание, тем лучше результат

💬 <b>Напишите ваше описание:</b>"""
        
        keyboard = get_back_keyboard()
        await callback.message.edit_text(prompt_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в generate_image_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(GenerationStates.waiting_prompt)
async def process_generation_prompt(message: Message, user: dict, state: FSMContext):
    """Обработка промпта для генерации"""
    try:
        prompt = message.text.strip()
        
        # Валидация промпта
        if len(prompt) < 3:
            await message.answer(
                "❌ Слишком короткое описание. Напишите более подробно, что вы хотите увидеть."
            )
            return
        
        if len(prompt) > 500:
            await message.answer(
                "❌ Слишком длинное описание. Максимум 500 символов."
            )
            return
        
        # Проверяем баланс еще раз
        fresh_user = await user_crud.get_by_telegram_id(user['telegram_id'])
        if not fresh_user or fresh_user.balance <= 0:
            await message.answer(
                "❌ Недостаточно средств! Пополните баланс для генерации изображений."
            )
            await state.clear()
            return
        
        # Списываем баланс
        new_balance = fresh_user.balance - 1
        await user_crud.update_balance(user['telegram_id'], new_balance)
        
        # Отправляем сообщение о начале генерации
        processing_msg = await message.answer(
            f"🎨 <b>Генерация началась!</b>\n\n"
            f"📝 <b>Описание:</b> {prompt[:120]}{'...' if len(prompt) > 120 else ''}\n"
            f"💰 <b>Новый баланс:</b> {new_balance} изображений\n\n"
            f"⏳ Ваш запрос отправлен в очередь на обработку...\n"
            f"⏱️ <b>Примерное время:</b> 1-3 минуты",
            reply_markup=get_back_keyboard()
        )
        
        # Определяем параметры генерации
        size = "512x512"
        priority = False
        
        if user.get('subscription_type') == "premium":
            size = "768x768"
            priority = True
        elif user.get('subscription_type') == "pro":
            size = "1024x1024" 
            priority = True
        
        # Создаем задачу генерации
        generation_task = {
            "user_id": user['telegram_id'],
            "prompt": prompt,
            "style": "realistic",  # По умолчанию реализм
            "quality": "standard",  # По умолчанию стандарт
            "size": size,
            "priority": priority,
            "message_id": processing_msg.message_id,
            "chat_id": message.chat.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "task_id": f"{user['telegram_id']}_{int(datetime.now(timezone.utc).timestamp())}"
        }
        
        # Добавляем в очередь Redis (Celery подхватит)
        await redis_client.lpush("generation_queue", json.dumps(generation_task))
        
        logger.info(
            f"Создана задача генерации для пользователя {user['telegram_id']}: "
            f"prompt='{prompt[:50]}...'"
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_generation_prompt: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "cancel_generation")
async def cancel_generation_handler(callback: CallbackQuery, user: dict):
    """Отмена генерации изображения"""
    try:
        # Возвращаем баланс (если генерация еще не началась)
        fresh_user = await user_crud.get_by_telegram_id(user['telegram_id'])
        if fresh_user:
            await user_crud.update_balance(
                user['telegram_id'], 
                fresh_user.balance + 1
            )
        
        keyboard = get_main_keyboard()
        
        await callback.message.edit_text(
            "❌ <b>Генерация отменена</b>\n\n"
            f"💰 Изображение возвращено на баланс\n"
            f"💎 Текущий баланс: {fresh_user.balance + 1} изображений",
            reply_markup=keyboard
        )
        await callback.answer("Генерация отменена")
        
    except Exception as e:
        logger.error(f"Ошибка в cancel_generation_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)
