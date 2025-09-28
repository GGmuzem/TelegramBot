"""
Клавиатуры для системы платежей
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from src.shared.config import settings


def get_buy_packages_keyboard(tariffs: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора пакетов для покупки"""
    buttons = []
    for tariff in tariffs:
        buttons.append([InlineKeyboardButton(
            text=f"💎 {tariff.name} - {tariff.price}₽ ({tariff.generations} изображений)",
            callback_data=f"buy_{tariff.id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад в меню",
        callback_data="back_to_main"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_package_details_keyboard(tariff_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с деталями пакета и способами оплаты"""
    
    keyboard_buttons = [
        # Способы оплаты
        [InlineKeyboardButton(
            text="💳 Банковская карта",
            callback_data=f"pay_{tariff_id}_card"
        )],
        [InlineKeyboardButton(
            text="📱 СБП (Система быстрых платежей)",
            callback_data=f"pay_{tariff_id}_sbp"
        )],
        [InlineKeyboardButton(
            text="🟢 SberPay",
            callback_data=f"pay_{tariff_id}_sberpay"
        )],
        [InlineKeyboardButton(
            text="🟡 ЮMoney",
            callback_data=f"pay_{tariff_id}_yoomoney"
        )]
    ]
    
    # WebApp для удобной оплаты
    if settings.BOT_WEBHOOK_URL:
        keyboard_buttons.insert(0, [InlineKeyboardButton(
            text="🌐 Удобная оплата (Web App)",
            web_app=WebAppInfo(url=f"{settings.BOT_WEBHOOK_URL}/webapp/payment/{tariff_id}")
        )])
    
    # Навигация
    keyboard_buttons.extend([
        [InlineKeyboardButton(
            text="◀️ К выбору пакетов",
            callback_data="buy_images"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_main"
        )]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_payment_method_keyboard(package: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора конкретного способа оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💳 Visa/MasterCard/МИР",
            callback_data=f"method_{package}_card"
        )],
        [InlineKeyboardButton(
            text="📱 СБП - оплата по QR",
            callback_data=f"method_{package}_qr"
        )],
        [InlineKeyboardButton(
            text="🟢 Через приложение Сбербанк",
            callback_data=f"method_{package}_sber"
        )],
        [InlineKeyboardButton(
            text="🟡 Через ЮMoney кошелек",
            callback_data=f"method_{package}_yoomoney"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к пакету",
            callback_data=f"buy_{package}"
        )]
    ])
    return keyboard


def get_payment_processing_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    """Клавиатура во время обработки платежа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔄 Проверить статус",
            callback_data=f"check_payment_{payment_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Отменить платеж",
            callback_data=f"cancel_payment_{payment_id}"
        )],
        [InlineKeyboardButton(
            text="💬 Помощь с оплатой",
            callback_data="payment_help"
        )]
    ])
    return keyboard


def get_payment_success_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешной оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎨 Генерировать изображение",
            callback_data="generate_image"
        )],
        [InlineKeyboardButton(
            text="📊 Мой баланс",
            callback_data="check_balance"
        )],
        [InlineKeyboardButton(
            text="🧾 История покупок",
            callback_data="payment_history"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_payment_failed_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    """Клавиатура при неуспешной оплате"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔄 Попробовать еще раз",
            callback_data=f"retry_payment_{payment_id}"
        )],
        [InlineKeyboardButton(
            text="💳 Выбрать другой способ",
            callback_data="buy_images"
        )],
        [InlineKeyboardButton(
            text="💬 Связаться с поддержкой",
            callback_data="payment_support"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_payment_history_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура истории платежей"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Все платежи",
            callback_data="show_all_payments"
        )],
        [InlineKeyboardButton(
            text="✅ Успешные",
            callback_data="show_successful_payments"
        )],
        [InlineKeyboardButton(
            text="❌ Неуспешные",
            callback_data="show_failed_payments"
        )],
        [InlineKeyboardButton(
            text="🧾 Запросить справку",
            callback_data="request_payment_report"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления подпиской"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐ Премиум подписка - 599₽/мес",
            callback_data="subscribe_premium"
        )],
        [InlineKeyboardButton(
            text="🔥 Профи подписка - 1299₽/мес",
            callback_data="subscribe_pro"
        )],
        [InlineKeyboardButton(
            text="📊 Текущая подписка",
            callback_data="check_subscription"
        )],
        [InlineKeyboardButton(
            text="❓ О подписках",
            callback_data="subscription_info"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_refund_request_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    """Клавиатура запроса возврата"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Подтвердить возврат",
            callback_data=f"confirm_refund_{payment_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="payment_history"
        )],
        [InlineKeyboardButton(
            text="💬 Связаться с поддержкой",
            callback_data="refund_support"
        )]
    ])
    return keyboard


def get_package_comparison_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура сравнения пакетов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📦 Базовый пакет",
            callback_data="compare_basic"
        ), InlineKeyboardButton(
            text="⭐ Премиум пакет",
            callback_data="compare_premium"
        )],
        [InlineKeyboardButton(
            text="🔥 Профи пакет",
            callback_data="compare_pro"
        ), InlineKeyboardButton(
            text="💎 Разовая покупка",
            callback_data="compare_once"
        )],
        [InlineKeyboardButton(
            text="💳 Перейти к оплате",
            callback_data="buy_images"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_promo_code_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для промокодов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎁 Ввести промокод",
            callback_data="enter_promo_code"
        )],
        [InlineKeyboardButton(
            text="📋 Мои промокоды",
            callback_data="my_promo_codes"
        )],
        [InlineKeyboardButton(
            text="🎯 Получить промокод",
            callback_data="get_promo_code"
        )],
        [InlineKeyboardButton(
            text="◀️ К оплате",
            callback_data="buy_images"
        )]
    ])
    return keyboard