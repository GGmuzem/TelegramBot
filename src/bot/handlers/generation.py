"""
Обработчик генерации AI изображений
"""
import json
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.bot.keyboards.main import (
    get_generation_keyboard, get_generation_result_keyboard,
    get_style_selection_keyboard, get_quality_selection_keyboard
)
from src.database.crud import UserCRUD, GenerationCRUD
from src.shared.redis_client import redis_client
from src.shared.config import QUALITY_SETTINGS, IMAGE_STYLES

logger = logging.getLogger(__name__)
router = Router()

# CRUD сервисы
user_crud = UserCRUD()
generation_crud = GenerationCRUD()


# FSM состояния
class GenerationStates(StatesGroup):
    waiting_prompt = State()
    selecting_style = State()
    selecting_quality = State()
    processing = State()


@router.callback_query(F.data == "generate_image")
async def generate_image_handler(callback: CallbackQuery, user: dict, state: FSMContext):
    """Начало процесса генерации изображения"""
    try:
        # Проверяем баланс
        if user['balance'] <= 0:
            from src.bot.keyboards.payment import get_buy_packages_keyboard
            keyboard = get_buy_packages_keyboard()
            
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
        
        prompt_text = f"""
🎨 <b>Генерация изображений</b>

💰 <b>Ваш баланс:</b> {user['balance']} изображений

📝 <b>Напишите описание изображения, которое хотите создать:</b>

🎯 <b>Примеры запросов:</b>
• "Красивый закат над морем в стиле импрессионизма"
• "Портрет девушки с голубыми глазами, фотореалистично"
• "Космический корабль в стиле киберпанк, неоновые цвета"
• "Милый котенок в стиле аниме"

⚙️ <b>Доступные стили:</b>
• Реализм (photorealistic)
• Аниме (anime style)
• Цифровое искусство (digital art)
• Портрет (portrait)
• Пейзаж (landscape)
• Абстракция (abstract)

✨ <b>Советы:</b>
• Используйте детальные описания
• Указывайте стиль и настроение
• Можете писать на русском языке
• Чем подробнее описание, тем лучше результат

💬 <b>Напишите ваше описание:</b>
"""
        
        from src.bot.keyboards.main import get_back_keyboard
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
        
        # Сохраняем промпт в состояние
        await state.update_data(prompt=prompt)
        
        # Предлагаем выбрать стиль
        style_keyboard = get_style_selection_keyboard()
        
        style_text = f"""
🎨 <b>Выберите стиль изображения:</b>

📝 <b>Ваш запрос:</b> {prompt[:100]}{'...' if len(prompt) > 100 else ''}

🎭 <b>Доступные стили:</b>
• 📷 <b>Реализм</b> - фотореалистичные изображения
• 🎌 <b>Аниме</b> - японская мультипликация
• 🎨 <b>Цифровое искусство</b> - художественная обработка
• 👤 <b>Портрет</b> - фокус на лицах людей
• 🏞️ <b>Пейзаж</b> - природные виды
• 🌀 <b>Абстракция</b> - абстрактное искусство

Выберите стиль ниже ⬇️
"""
        
        await state.set_state(GenerationStates.selecting_style)
        await message.answer(style_text, reply_markup=style_keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в process_generation_prompt: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке запроса. Попробуйте еще раз."
        )
        await state.clear()


@router.callback_query(GenerationStates.selecting_style, F.data.startswith("style_"))
async def process_style_selection(callback: CallbackQuery, user: dict, state: FSMContext):
    """Обработка выбора стиля"""
    try:
        style = callback.data.replace("style_", "")
        await state.update_data(style=style)
        
        # Предлагаем выбрать качество
        quality_keyboard = get_quality_selection_keyboard()
        
        # Определяем доступные качества в зависимости от подписки
        available_qualities = ["fast", "standard"]
        
        if user.get('subscription_type') in ["premium", "pro"]:
            available_qualities.append("high")
        
        if user.get('subscription_type') == "pro":
            available_qualities.append("ultra")
        
        data = await state.get_data()
        prompt = data.get('prompt', '')
        
        quality_text = f"""
⚙️ <b>Выберите качество генерации:</b>

📝 <b>Запрос:</b> {prompt[:80]}{'...' if len(prompt) > 80 else ''}
🎨 <b>Стиль:</b> {IMAGE_STYLES.get(style, {}).get('name', style)}

💎 <b>Доступные качества:</b>

⚡ <b>Быстро</b> (8 шагов) - ~5-10 секунд
⚙️ <b>Стандарт</b> (20 шагов) - ~15-25 секунд
"""
        
        if "high" in available_qualities:
            quality_text += "✨ <b>Высокое</b> (35 шагов) - ~35-50 секунд\n"
        
        if "ultra" in available_qualities:
            quality_text += "💎 <b>Ультра</b> (50 шагов) - ~45-70 секунд\n"
        
        quality_text += f"\n💰 <b>Стоимость:</b> 1 изображение"
        
        await state.set_state(GenerationStates.selecting_quality)
        await callback.message.edit_text(quality_text, reply_markup=quality_keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_style_selection: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(GenerationStates.selecting_quality, F.data.startswith("quality_"))
async def process_quality_selection(callback: CallbackQuery, user: dict, state: FSMContext):
    """Обработка выбора качества и запуск генерации"""
    try:
        quality = callback.data.replace("quality_", "")
        
        # Проверяем доступность качества
        if quality in ["high", "ultra"] and user.get('subscription_type') not in ["premium", "pro"]:
            await callback.answer(
                "❌ Это качество доступно только для премиум подписчиков", 
                show_alert=True
            )
            return
        
        if quality == "ultra" and user.get('subscription_type') != "pro":
            await callback.answer(
                "❌ Ультра качество доступно только для профи подписчиков",
                show_alert=True  
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        prompt = data.get('prompt', '')
        style = data.get('style', 'realistic')
        
        # Финальная проверка баланса и списание
        fresh_user = await user_crud.get_by_telegram_id(user['telegram_id'])
        if not fresh_user or fresh_user.balance <= 0:
            await callback.message.edit_text(
                "❌ Недостаточно средств! Пополните баланс для генерации.",
                reply_markup=get_back_keyboard()
            )
            await state.clear()
            return
        
        # Списываем баланс
        new_balance = fresh_user.balance - 1
        await user_crud.update_balance(user['telegram_id'], new_balance)
        
        # Отправляем сообщение о начале генерации
        processing_keyboard = get_generation_keyboard()
        
        processing_msg = await callback.message.edit_text(
            f"🎨 <b>Генерация началась!</b>\n\n"
            f"📝 <b>Описание:</b> {prompt[:120]}{'...' if len(prompt) > 120 else ''}\n"
            f"🎨 <b>Стиль:</b> {IMAGE_STYLES.get(style, {}).get('name', style)}\n"
            f"⚙️ <b>Качество:</b> {QUALITY_SETTINGS.get(quality, {}).get('name', quality)}\n"
            f"💰 <b>Новый баланс:</b> {new_balance} изображений\n\n"
            f"⏳ Определяю позицию в очереди...",
            reply_markup=processing_keyboard
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
            "style": style,
            "quality": quality,
            "size": size,
            "priority": priority,
            "message_id": processing_msg.message_id,
            "chat_id": callback.message.chat.id,
            "created_at": datetime.utcnow().isoformat(),
            "task_id": f"{user['telegram_id']}_{int(datetime.utcnow().timestamp())}"
        }
        
        # Добавляем в очередь
        queue_name = "priority_queue" if priority else "generation_queue"
        await redis_client.add_to_generation_queue(generation_task, priority)
        
        # Получаем позицию в очереди
        queue_position = await redis_client.get_queue_length(queue_name)
        estimated_time = queue_position * 25  # Примерно 25 секунд на изображение
        
        await processing_msg.edit_text(
            f"🎨 <b>Ваш запрос принят!</b>\n\n"
            f"📝 <b>Описание:</b> {prompt[:120]}{'...' if len(prompt) > 120 else ''}\n"
            f"🎨 <b>Стиль:</b> {IMAGE_STYLES.get(style, {}).get('name', style)}\n"
            f"⚙️ <b>Качество:</b> {QUALITY_SETTINGS.get(quality, {}).get('name', quality)}\n"
            f"📐 <b>Размер:</b> {size}\n\n"
            f"📊 <b>Позиция в очереди:</b> {queue_position}\n"
            f"⏱️ <b>Примерное время:</b> {estimated_time // 60}м {estimated_time % 60}с\n"
            f"💰 <b>Новый баланс:</b> {new_balance} изображений",
            reply_markup=processing_keyboard
        )
        
        # Очищаем состояние
        await state.clear()
        
        logger.info(
            f"Создана задача генерации для пользователя {user['telegram_id']}: "
            f"{style}/{quality}/{size}"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_quality_selection: {e}")
        await callback.answer("Произошла ошибка при создании задачи", show_alert=True)
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
        
        from src.bot.keyboards.main import get_main_keyboard
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


@router.callback_query(F.data == "history")
async def history_handler(callback: CallbackQuery, user: dict):
    """История генераций пользователя"""
    try:
        # Получаем последние генерации
        generations = await generation_crud.get_user_generations(
            user['telegram_id'], 
            limit=10
        )
        
        if not generations:
            from src.bot.keyboards.main import get_main_keyboard
            keyboard = get_main_keyboard()
            
            await callback.message.edit_text(
                "📊 <b>История генераций</b>\n\n"
                "У вас пока нет сгенерированных изображений.\n"
                "Начните с создания первого изображения!",
                reply_markup=keyboard
            )
            await callback.answer()
            return
        
        history_text = "📊 <b>История генераций</b>\n\n"
        
        # Показываем последние 5 генераций
        for i, gen in enumerate(generations[:5], 1):
            status_emoji = {
                "completed": "✅",
                "failed": "❌", 
                "processing": "⏳",
                "pending": "🕐"
            }.get(gen.status, "❓")
            
            prompt_preview = gen.prompt[:50] + "..." if len(gen.prompt) > 50 else gen.prompt
            date_str = gen.created_at.strftime('%d.%m %H:%M')
            
            history_text += f"{i}. {status_emoji} <i>{prompt_preview}</i>\n"
            history_text += f"   📅 {date_str} | 🎨 {gen.style} | 📐 {gen.size}\n\n"
        
        from src.bot.keyboards.main import get_history_keyboard
        keyboard = get_history_keyboard(has_more=len(generations) > 5)
        
        await callback.message.edit_text(history_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в history_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)