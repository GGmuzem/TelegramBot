"""
Клавиатуры для главного меню
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from src.shared.config import settings


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Основная клавиатура главного меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎨 Генерировать изображение", 
            callback_data="generate_image"
        )],
        [InlineKeyboardButton(
            text="💳 Купить изображения", 
            callback_data="buy_images"
        )],
        [InlineKeyboardButton(
            text="💰 Мой баланс", 
            callback_data="check_balance"
        ), InlineKeyboardButton(
            text="📊 Статистика", 
            callback_data="statistics"
        )],
        [InlineKeyboardButton(
            text="📋 История", 
            callback_data="history"
        ), InlineKeyboardButton(
            text="❓ Помощь", 
            callback_data="help"
        )]
    ])
    return keyboard


def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для экрана баланса"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💳 Пополнить баланс", 
            callback_data="buy_images"
        )],
        [InlineKeyboardButton(
            text="🎨 Генерировать изображение", 
            callback_data="generate_image"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в меню", 
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура с кнопкой "Назад" """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Назад в меню", 
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_generation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для процесса генерации"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отменить генерацию", 
            callback_data="cancel_generation"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в меню", 
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_generation_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешной генерации"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔄 Генерировать еще", 
            callback_data="generate_image"
        )],
        [InlineKeyboardButton(
            text="💳 Купить изображения", 
            callback_data="buy_images"
        )],
        [InlineKeyboardButton(
            text="📊 История", 
            callback_data="history"
        ), InlineKeyboardButton(
            text="🏠 Меню", 
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_style_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора стиля изображения"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📷 Реализм", 
            callback_data="style_realistic"
        ), InlineKeyboardButton(
            text="🎌 Аниме", 
            callback_data="style_anime"
        )],
        [InlineKeyboardButton(
            text="🎨 Цифровое искусство", 
            callback_data="style_art"
        ), InlineKeyboardButton(
            text="👤 Портрет", 
            callback_data="style_portrait"
        )],
        [InlineKeyboardButton(
            text="🏞️ Пейзаж", 
            callback_data="style_landscape"
        ), InlineKeyboardButton(
            text="🌀 Абстракция", 
            callback_data="style_abstract"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад", 
            callback_data="back_to_main"
        )]
    ])
    return keyboard


def get_quality_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора качества генерации"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚡ Быстро (8 шагов)", 
            callback_data="quality_fast"
        )],
        [InlineKeyboardButton(
            text="⚙️ Стандарт (20 шагов)", 
            callback_data="quality_standard"
        )],
        [InlineKeyboardButton(
            text="✨ Высокое (35 шагов)", 
            callback_data="quality_high"
        )],
        [InlineKeyboardButton(
            text="💎 Ультра (50 шагов)", 
            callback_data="quality_ultra"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад", 
            callback_data="generate_image"
        )]
    ])
    return keyboard


def get_history_keyboard(has_more: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для истории генераций"""
    buttons = []
    
    if has_more:
        buttons.append([InlineKeyboardButton(
            text="📋 Показать все", 
            callback_data="show_full_history"
        )])
    
    buttons.extend([
        [InlineKeyboardButton(
            text="🎨 Генерировать еще", 
            callback_data="generate_image"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в меню", 
            callback_data="back_to_main"
        )]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для админ панели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Статистика системы", 
            callback_data="admin_stats"
        )],
        [InlineKeyboardButton(
            text="👥 Управление пользователями", 
            callback_data="admin_users"
        )],
        [InlineKeyboardButton(
            text="💰 Финансовые отчеты", 
            callback_data="admin_finance"
        )],
        [InlineKeyboardButton(
            text="🎨 Мониторинг генерации", 
            callback_data="admin_generation"
        )],
        [InlineKeyboardButton(
            text="📝 Логи системы", 
            callback_data="admin_logs"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в меню", 
            callback_data="back_to_main"
        )]
    ])
    return keyboard