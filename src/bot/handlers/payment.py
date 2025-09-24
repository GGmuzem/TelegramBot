"""
Обработчик платежей в Telegram боте
"""
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.bot.keyboards.payment import (
    get_buy_packages_keyboard, get_package_details_keyboard,
    get_payment_processing_keyboard, get_payment_success_keyboard,
    get_payment_failed_keyboard, get_payment_history_keyboard
)
from src.database.crud import UserCRUD, PaymentCRUD
from src.payment.providers.yookassa import YooKassaProvider
from src.shared.config import PACKAGES, settings
from src.shared.redis_client import redis_client

logger = logging.getLogger(__name__)
router = Router()

# Сервисы
user_crud = UserCRUD()
payment_crud = PaymentCRUD()
yookassa_provider = YooKassaProvider()


# FSM состояния для платежей
class PaymentStates(StatesGroup):
    selecting_package = State()
    selecting_method = State()
    processing_payment = State()
    entering_promo_code = State()


@router.callback_query(F.data == "buy_images")
async def buy_images_handler(callback: CallbackQuery, user: dict):
    """Главное меню покупки изображений"""
    try:
        keyboard = get_buy_packages_keyboard()
        
        packages_text = f"""
💳 <b>Купить изображения для генерации</b>

👤 <b>Ваш баланс:</b> {user['balance']} изображений

🎯 <b>Доступные пакеты:</b>

💎 <b>Разовая генерация - 49₽</b>
• 1 изображение
• Обычная очередь
• Качество Standard
• Размер 512x512

📦 <b>Базовый пакет - 299₽</b>
• 10 изображений
• Срок действия: 30 дней
• Качество Standard
• Размер 512x512

⭐ <b>Премиум пакет - 599₽</b>
• 25 изображений
• Приоритетная очередь
• Качество High
• Размер 768x768
• Срок действия: 60 дней

🔥 <b>Профи пакет - 1299₽</b>
• 60 изображений
• Без очереди (мгновенная генерация)
• Качество Ultra
• Размер 1024x1024
• Срок действия: 90 дней

🔒 <b>Безопасность:</b>
• PCI DSS Level 1 защита
• Фискализация по 54-ФЗ
• Автоматические чеки на email
• Возврат в течение 14 дней

Выберите пакет ⬇️
"""
        
        await callback.message.edit_text(packages_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в buy_images_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("buy_"))
async def package_selection_handler(callback: CallbackQuery, user: dict, state: FSMContext):
    """Обработка выбора конкретного пакета"""
    try:
        package = callback.data.replace("buy_", "")
        
        if package not in PACKAGES:
            await callback.answer("Неизвестный пакет", show_alert=True)
            return
        
        # Сохраняем выбранный пакет
        await state.update_data(selected_package=package)
        
        package_info = PACKAGES[package]
        keyboard = get_package_details_keyboard(package)
        
        # Формируем детальное описание пакета
        features_text = ""
        if package == "premium":
            features_text = """
✅ <b>Особенности Премиум:</b>
• Приоритетная очередь (в 3 раза быстрее)
• Высокое качество (35 шагов генерации)
• Размер изображений 768x768
• Поддержка всех стилей
• Техподдержка в приоритете
"""
        elif package == "pro":
            features_text = """
✅ <b>Особенности Профи:</b>
• Мгновенная генерация (без очереди)
• Максимальное качество (50 шагов)
• Размер изображений 1024x1024
• Эксклюзивные стили
• Персональная поддержка 24/7
• Возможность заказать custom модель
"""
        
        package_text = f"""
📦 <b>{package_info['name']}</b>

💰 <b>Стоимость:</b> {package_info['price']}₽
🎨 <b>Изображений:</b> {package_info['images']}
⏱️ <b>Срок действия:</b> {package_info.get('duration', 'Не ограничен')}
📏 <b>Размер:</b> {package_info.get('size', '512x512')}
⚙️ <b>Качество:</b> {package_info.get('quality', 'Standard')}

{features_text}

🔒 <b>Способы оплаты:</b>
• Банковские карты (Visa/MC/МИР)
• СБП - Система быстрых платежей  
• SberPay
• ЮMoney

🧾 <b>Документы:</b>
• Фискальный чек по 54-ФЗ
• Справка об оплате
• Возврат в течение 14 дней

Выберите способ оплаты ⬇️
"""
        
        await callback.message.edit_text(package_text, reply_markup=keyboard)
        await state.set_state(PaymentStates.selecting_method)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в package_selection_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(PaymentStates.selecting_method, F.data.startswith("pay_"))
async def payment_method_handler(callback: CallbackQuery, user: dict, state: FSMContext):
    """Обработка выбора способа оплаты"""
    try:
        # Парсим callback_data: pay_{package}_{method}
        data_parts = callback.data.split("_")
        if len(data_parts) != 3:
            await callback.answer("Неверный формат данных", show_alert=True)
            return
        
        _, package, method = data_parts
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        selected_package = state_data.get('selected_package')
        
        if package != selected_package:
            await callback.answer("Несоответствие данных", show_alert=True)
            return
        
        # Сохраняем метод оплаты
        await state.update_data(payment_method=method)
        
        # Создаем платеж
        processing_msg = await callback.message.edit_text(
            "💳 <b>Создание платежа...</b>\n\n"
            "⏳ Пожалуйста, подождите...",
            reply_markup=None
        )
        
        try:
            # Создаем платеж через ЮKassa
            payment_result = await yookassa_provider.create_payment(
                user_id=user['telegram_id'],
                package=package,
                method=method,
                return_url=f"{settings.BOT_WEBHOOK_URL}/webapp/success"
            )
            
            if not payment_result or not payment_result.get('success'):
                raise Exception(payment_result.get('error', 'Неизвестная ошибка создания платежа'))
            
            payment_id = payment_result['payment_id']
            confirmation_url = payment_result['confirmation_url']
            amount = payment_result['amount']
            
            # Сохраняем ID платежа в состояние
            await state.update_data(payment_id=payment_id)
            
            # Формируем сообщение с инструкциями
            method_instructions = {
                'card': '💳 Оплата банковской картой',
                'sbp': '📱 Оплата через СБП',
                'sberpay': '🟢 Оплата через SberPay',
                'yoomoney': '🟡 Оплата через ЮMoney'
            }
            
            keyboard = get_payment_processing_keyboard(payment_id)
            
            payment_text = f"""
💳 <b>Платеж создан успешно!</b>

📦 <b>Пакет:</b> {PACKAGES[package]['name']}
💰 <b>Сумма:</b> {amount}₽
🔢 <b>ID платежа:</b> <code>{payment_id}</code>
🔄 <b>Способ:</b> {method_instructions.get(method, method)}

🔗 <b>Для оплаты нажмите кнопку ниже</b>

⏱️ <b>Время на оплату:</b> 15 минут
🔒 <b>Платеж защищен по стандарту PCI DSS</b>

После успешной оплаты изображения автоматически добавятся на ваш баланс.
"""
            
            # Добавляем кнопку оплаты
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💳 Оплатить",
                    url=confirmation_url
                )],
                [InlineKeyboardButton(
                    text="🔄 Проверить статус",
                    callback_data=f"check_payment_{payment_id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить платеж",
                    callback_data=f"cancel_payment_{payment_id}"
                )]
            ])
            
            await processing_msg.edit_text(payment_text, reply_markup=payment_keyboard)
            await state.set_state(PaymentStates.processing_payment)
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            
            error_text = f"""
❌ <b>Ошибка создания платежа</b>

Не удалось создать платеж: {str(e)}

Попробуйте:
• Выбрать другой способ оплаты
• Повторить попытку через несколько минут
• Обратиться в поддержку

Средства не были списаны.
"""
            
            from src.bot.keyboards.main import get_back_keyboard
            keyboard = get_back_keyboard()
            
            await processing_msg.edit_text(error_text, reply_markup=keyboard)
            await state.clear()
            await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в payment_method_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery, user: dict):
    """Проверка статуса платежа"""
    try:
        payment_id = callback.data.replace("check_payment_", "")
        
        # Получаем статус платежа
        payment = await payment_crud.get_by_payment_id(payment_id)
        
        if not payment:
            await callback.answer("Платеж не найден", show_alert=True)
            return
        
        # Проверяем актуальный статус в ЮKassa
        status_result = await yookassa_provider.check_payment_status(payment_id)
        
        if status_result and status_result.get('status') == 'succeeded':
            # Платеж успешен
            package_info = PACKAGES.get(payment.package_type, {})
            images_count = package_info.get('images', 1)
            
            success_text = f"""
✅ <b>Платеж успешно завершен!</b>

📦 <b>Пакет:</b> {package_info.get('name', 'Неизвестный')}
💰 <b>Сумма:</b> {payment.amount}₽
🎨 <b>Изображений добавлено:</b> {images_count}

💎 <b>Ваш новый баланс:</b> {user['balance'] + images_count} изображений

🧾 Чек отправлен на email
📧 ID транзакции: <code>{payment_id}</code>

Теперь можете генерировать изображения!
"""
            
            keyboard = get_payment_success_keyboard()
            await callback.message.edit_text(success_text, reply_markup=keyboard)
            
        elif status_result and status_result.get('status') in ['canceled', 'failed']:
            # Платеж неуспешен
            error_reason = status_result.get('cancellation_details', {}).get('reason', 'Неизвестная причина')
            
            failed_text = f"""
❌ <b>Платеж не выполнен</b>

🔢 <b>ID платежа:</b> <code>{payment_id}</code>
⚠️ <b>Причина:</b> {error_reason}

💰 Средства не были списаны
⏰ Можете попробовать оплатить еще раз

Если проблема повторяется, обратитесь в поддержку.
"""
            
            keyboard = get_payment_failed_keyboard(payment_id)
            await callback.message.edit_text(failed_text, reply_markup=keyboard)
            
        else:
            # Платеж все еще обрабатывается
            await callback.answer(
                "Платеж еще обрабатывается. Попробуйте через минуту.",
                show_alert=True
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка проверки статуса платежа: {e}")
        await callback.answer("Ошибка проверки статуса", show_alert=True)


@router.callback_query(F.data.startswith("cancel_payment_"))
async def cancel_payment_handler(callback: CallbackQuery, user: dict):
    """Отмена платежа"""
    try:
        payment_id = callback.data.replace("cancel_payment_", "")
        
        # Отменяем платеж в ЮKassa
        cancel_result = await yookassa_provider.cancel_payment(payment_id)
        
        if cancel_result and cancel_result.get('success'):
            cancel_text = f"""
❌ <b>Платеж отменен</b>

🔢 <b>ID платежа:</b> <code>{payment_id}</code>

✅ Средства не были списаны
💳 Можете выбрать другой способ оплаты

Если у вас есть вопросы, обратитесь в поддержку.
"""
        else:
            cancel_text = f"""
⚠️ <b>Не удалось отменить платеж</b>

🔢 <b>ID платежа:</b> <code>{payment_id}</code>

Возможно, платеж уже обрабатывается.
Проверьте статус или обратитесь в поддержку.
"""
        
        from src.bot.keyboards.main import get_back_keyboard
        keyboard = get_back_keyboard()
        
        await callback.message.edit_text(cancel_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка отмены платежа: {e}")
        await callback.answer("Ошибка отмены платежа", show_alert=True)


@router.callback_query(F.data == "payment_history")
async def payment_history_handler(callback: CallbackQuery, user: dict):
    """История платежей пользователя"""
    try:
        # Получаем последние платежи пользователя
        payments = await payment_crud.get_user_payments(user['telegram_id'], limit=10)
        
        if not payments:
            history_text = f"""
📋 <b>История платежей</b>

У вас пока нет платежей.
Купите первый пакет изображений!
"""
        else:
            history_text = f"""
📋 <b>История платежей</b>

👤 <b>Пользователь:</b> {user['full_name']}
💰 <b>Общая сумма:</b> {user['total_spent']}₽

<b>Последние платежи:</b>
"""
            
            for i, payment in enumerate(payments, 1):
                status_emoji = {
                    "succeeded": "✅",
                    "pending": "⏳", 
                    "canceled": "❌",
                    "failed": "❌"
                }.get(payment.status.value, "❓")
                
                date_str = payment.created_at.strftime('%d.%m.%Y %H:%M')
                package_name = PACKAGES.get(payment.package_type, {}).get('name', payment.package_type)
                
                history_text += (
                    f"\n{i}. {status_emoji} <b>{package_name}</b>\n"
                    f"   💰 {payment.amount}₽ • 📅 {date_str}\n"
                    f"   🔢 <code>{payment.payment_id}</code>"
                )
                
                if i >= 5:  # Показываем только последние 5
                    break
        
        keyboard = get_payment_history_keyboard()
        await callback.message.edit_text(history_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в payment_history_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "payment_support")
async def payment_support_handler(callback: CallbackQuery, user: dict):
    """Поддержка по платежам"""
    support_text = f"""
💬 <b>Поддержка по платежам</b>

📞 <b>Способы связи:</b>
• Telegram: @ai_support_bot
• Email: support@aibot.ru
• Телефон: +7 (495) 123-45-67

🕐 <b>Время работы:</b>
Круглосуточно, 24/7

📋 <b>Для быстрого решения укажите:</b>
• Ваш ID: <code>{user['telegram_id']}</code>
• ID платежа (если есть)
• Описание проблемы
• Способ оплаты

⚡ <b>Частые вопросы:</b>
• Деньги списались, но баланс не пополнился
• Ошибка при оплате картой
• Не приходит чек
• Вопросы возврата

🔒 <b>Безопасность:</b>
Никогда не сообщайте данные карт в поддержку!
"""
    
    from src.bot.keyboards.main import get_back_keyboard
    keyboard = get_back_keyboard()
    
    await callback.message.edit_text(support_text, reply_markup=keyboard)
    await callback.answer()