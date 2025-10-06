"""
Обработчик команды /start и основного меню
"""
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from src.bot.keyboards.main import get_main_keyboard
from src.database.crud import UserCRUD, GenerationCRUD
from src.payment.service import payment_service

logger = logging.getLogger(__name__)
router = Router()

user_crud = UserCRUD()

@router.message(CommandStart())
async def start_handler(message: Message, user: dict):
    """Обработчик команды /start"""
    try:
        keyboard = get_main_keyboard()
        tariffs = await payment_service.get_tariffs()
        tariffs_text = "\n".join([f"- {t.name} ({t.price}₽)" for t in tariffs])
        
        welcome_text = f"""🤖 <b>Добро пожаловать!</b>

👋 Привет, <b>{user['first_name']}</b>!

Ваш баланс: {user['balance']} генераций.

Доступные тарифы:
{tariffs_text}

Выберите действие:"""
        
        await message.answer(welcome_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}")
        await message.answer("Произошла ошибка при запуске.")

@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery, user: dict):
    """Возврат в главное меню"""
    try:
        keyboard = get_main_keyboard()
        main_menu_text = f"""🏠 <b>Главное меню</b>

💰 <b>Баланс:</b> {user['balance']} изображений

Выберите действие:"""
        await callback.message.edit_text(main_menu_text, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в back_to_main_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)

@router.message(Command("history"))
@router.callback_query(F.data == "history")
async def history_handler(message: Message | CallbackQuery, user: dict):
    """История генераций"""
    from src.database.connection import get_session
    generation_crud = GenerationCRUD()
    
    async with get_session() as session:
        generations = await generation_crud.get_user_generations(session, user['telegram_id'], limit=5)
    
    if not generations:
        text = "У вас еще нет генераций."
    else:
        text = "<b>Последние 5 генераций:</b>\n\n"
        for gen in generations:
            text += f"- <code>{gen.prompt[:30]}...</code> ({gen.status})\n"

    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text)
    else:
        await message.answer(text)

@router.message(Command("support"))
@router.callback_query(F.data == "support")
async def support_handler(message: Message | CallbackQuery, user: dict):
    """Поддержка"""
    text = f"""💬 <b>Поддержка</b>

Свяжитесь с нами: @ai_support_bot
Ваш ID: <code>{user['telegram_id']}</code>"""
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text)
    else:
        await message.answer(text)

@router.callback_query(F.data == "check_balance")
async def check_balance_handler(callback: CallbackQuery, user: dict):
    """Проверка баланса"""
    from src.bot.keyboards.main import get_balance_keyboard
    text = f"""💰 <b>Ваш баланс</b>

💎 Доступно генераций: <b>{user['balance']}</b>
📊 Всего сгенерировано: <b>{user['total_generations']}</b>
💵 Всего потрачено: <b>{user['total_spent']:.2f}₽</b>

Хотите пополнить баланс?"""
    await callback.message.edit_text(text, reply_markup=get_balance_keyboard())
    await callback.answer()

@router.callback_query(F.data == "statistics")
async def statistics_handler(callback: CallbackQuery, user: dict):
    """Статистика пользователя"""
    from src.bot.keyboards.main import get_back_keyboard
    text = f"""📊 <b>Ваша статистика</b>

👤 ID: <code>{user['telegram_id']}</code>
📅 Дата регистрации: {user['created_at'].strftime('%d.%m.%Y')}
🎨 Всего генераций: <b>{user['total_generations']}</b>
💰 Текущий баланс: <b>{user['balance']}</b> изображений
💵 Всего потрачено: <b>{user['total_spent']:.2f}₽</b>

{"⭐ Подписка: " + user['subscription_type'] if user.get('subscription_type') else ""}"""
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    """Помощь"""
    from src.bot.keyboards.main import get_back_keyboard
    text = """❓ <b>Помощь</b>

<b>Как пользоваться ботом:</b>

1️⃣ <b>Генерация изображений</b>
   Нажмите "🎨 Генерировать изображение", введите описание и выберите стиль

2️⃣ <b>Покупка генераций</b>
   Нажмите "💳 Купить изображения" и выберите пакет

3️⃣ <b>Баланс</b>
   Проверяйте свой баланс в разделе "💰 Мой баланс"

<b>Поддержка:</b> @ai_support_bot

<b>Тарифы:</b>
• Базовый: 100₽ - 10 изображений
• Стандарт: 300₽ - 35 изображений
• Премиум: 500₽ - 65 изображений"""
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()