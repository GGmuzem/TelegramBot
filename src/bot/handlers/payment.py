"""
Обработчик платежей в Telegram боте
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.bot.keyboards.payment import get_buy_packages_keyboard, get_package_details_keyboard
from src.payment.service import payment_service
from src.shared.config import settings

logger = logging.getLogger(__name__)
router = Router()

class PaymentStates(StatesGroup):
    selecting_package = State()
    selecting_method = State()

@router.callback_query(F.data == "buy_images")
async def buy_images_handler(callback: CallbackQuery, state: FSMContext):
    tariffs = await payment_service.get_tariffs()
    text = f"""💳 <b>Купить изображения</b>

Выберите пакет:"""
    keyboard = get_buy_packages_keyboard(tariffs)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PaymentStates.selecting_package)
    await callback.answer()

@router.callback_query(PaymentStates.selecting_package, F.data.startswith("buy_"))
async def tariff_selection_handler(callback: CallbackQuery, state: FSMContext):
    tariff_id = int(callback.data.replace("buy_", ""))
    tariffs = await payment_service.get_tariffs()
    tariff = next((t for t in tariffs if t.id == tariff_id), None)
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await state.update_data(selected_tariff_id=tariff_id)
    
    text = f"""📦 <b>{tariff.name}</b> - {tariff.price}₽

{tariff.generations} генераций, размер {tariff.image_size}

Выберите способ оплаты:"""
    keyboard = get_package_details_keyboard(tariff_id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PaymentStates.selecting_method)
    await callback.answer()

@router.callback_query(PaymentStates.selecting_method, F.data.startswith("pay_"))
async def payment_method_handler(callback: CallbackQuery, user: dict, state: FSMContext):
    data = await state.get_data()
    tariff_id = data.get('selected_tariff_id')
    _, _, method = callback.data.split("_")

    result = await payment_service.create_payment(
        user_id=user['telegram_id'],
        tariff_id=tariff_id,
        method=method,
        return_url=f"{settings.BOT_WEBHOOK_URL}/webapp/success"
    )

    if result.get('success'):
        await callback.message.edit_text(
            f"Платеж создан! <a href='{result['confirmation_url']}'>Нажмите для оплаты</a>",
            disable_web_page_preview=True
        )
    else:
        await callback.message.edit_text(f"Ошибка создания платежа: {result.get('error')}")
    
    await state.clear()
    await callback.answer()