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
    generation_crud = GenerationCRUD()
    generations = await generation_crud.get_user_generations(user['telegram_id'], limit=5)
    
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