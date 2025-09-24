"""
Обработчик команды /start и основного меню
"""
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.keyboards.main import get_main_keyboard
from src.database.crud import UserCRUD
from src.shared.config import PACKAGES

logger = logging.getLogger(__name__)
router = Router()

# CRUD для работы с пользователями
user_crud = UserCRUD()


@router.message(CommandStart())
async def start_handler(message: Message, user: dict):
    """Обработчик команды /start"""
    try:
        # Получаем пользователя из middleware
        keyboard = get_main_keyboard()
        
        welcome_text = f"""
🤖 <b>Добро пожаловать в AI Image Generator Bot!</b>

👋 Привет, <b>{user['first_name']}</b>!

🎯 <b>Ваш ID:</b> <code>{user['telegram_id']}</code>
💰 <b>Баланс:</b> {user['balance']} изображений
📅 <b>С нами с:</b> {user['created_at'].strftime('%d.%m.%Y')}

🚀 <b>Что я умею:</b>
• Генерировать изображения по описанию на русском языке
• Поддерживаю разные стили: реализм, аниме, арт, портрет
• Работаю на мощных RTX 5080 для быстрой генерации
• Принимаю оплату картами, СБП, SberPay, ЮMoney

💡 <b>Тарифы:</b>
💎 Разовая генерация: 49₽ (1 изображение)
📦 Базовый пакет: 299₽ (10 изображений)
⭐ Премиум пакет: 599₽ (25 изображений + приоритет)
🔥 Профи пакет: 1299₽ (60 изображений + без очереди)

Выберите действие ниже ⬇️
"""
        
        await message.answer(welcome_text, reply_markup=keyboard)
        logger.info(f"Пользователь {user['telegram_id']} запустил бота")
        
    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}")
        await message.answer(
            "Произошла ошибка при запуске. Попробуйте позже.", 
            reply_markup=get_main_keyboard()
        )


@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery, user: dict):
    """Возврат в главное меню"""
    try:
        keyboard = get_main_keyboard()
        
        main_menu_text = f"""
🏠 <b>Главное меню</b>

👤 <b>Пользователь:</b> {user['full_name']}
💰 <b>Баланс:</b> {user['balance']} изображений
📊 <b>Всего сгенерировано:</b> {user['total_generations']}

Выберите действие:
"""
        
        await callback.message.edit_text(
            main_menu_text, 
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в back_to_main_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "check_balance")
async def check_balance_handler(callback: CallbackQuery, user: dict):
    """Проверка баланса пользователя"""
    try:
        # Получаем актуальные данные пользователя
        fresh_user = await user_crud.get_by_telegram_id(user['telegram_id'])
        
        subscription_info = ""
        if fresh_user and fresh_user.subscription_type and fresh_user.has_active_subscription:
            subscription_info = (
                f"\n🎯 <b>Подписка:</b> {fresh_user.subscription_type.upper()}\n"
                f"⏰ <b>Действует до:</b> {fresh_user.subscription_expires.strftime('%d.%m.%Y %H:%M')}"
            )
        
        balance_text = f"""
💰 <b>Информация о балансе</b>

👤 <b>Пользователь:</b> {user['full_name']}
🆔 <b>ID:</b> <code>{user['telegram_id']}</code>
💎 <b>Баланс:</b> {fresh_user.balance if fresh_user else user['balance']} изображений{subscription_info}

📊 <b>Статистика:</b>
• Всего сгенерировано: {user['total_generations']}
• Всего потрачено: {user['total_spent']}₽
• Дата регистрации: {user['created_at'].strftime('%d.%m.%Y')}
• Последняя активность: {user.get('last_activity', 'Сейчас')}

{"🔋 Баланс в порядке!" if user['balance'] > 0 else "⚠️ Необходимо пополнить баланс"}
"""
        
        from src.bot.keyboards.main import get_balance_keyboard
        keyboard = get_balance_keyboard()
        
        await callback.message.edit_text(balance_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в check_balance_handler: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    """Справка по использованию бота"""
    help_text = f"""
❓ <b>Справка по использованию AI Image Generator Bot</b>

🎨 <b>Как генерировать изображения:</b>
1. Нажмите "Генерировать изображение"
2. Опишите, что хотите увидеть
3. Ждите результат (15-60 секунд)
4. Получите готовое изображение

💳 <b>Как купить изображения:</b>
1. Нажмите "Купить изображения"
2. Выберите подходящий тариф
3. Оплатите картой, СБП или ЮMoney
4. Баланс пополнится автоматически

✨ <b>Советы для лучших результатов:</b>
• Описывайте детально: цвета, стиль, настроение
• Используйте конкретные термины
• Указывайте художественный стиль
• Пишите на русском или английском

🎯 <b>Примеры хороших промптов:</b>
• "Портрет девушки с зелеными глазами, фотореалистично"
• "Космический пейзаж в стиле ретро-футуризма"
• "Милый щенок в стиле Disney, мультяшный"

⚙️ <b>Доступные стили:</b>
• Реализм - фотореалистичные изображения
• Аниме - японская мультипликация
• Арт - цифровая живопись
• Портрет - фокус на лицах и людях
• Пейзаж - природа и места
• Абстракция - абстрактное искусство

💰 <b>Тарифы:</b>
• Разовая - 49₽ за 1 изображение
• Базовый - 299₽ за 10 изображений
• Премиум - 599₽ за 25 + приоритет
• Профи - 1299₽ за 60 + без очереди

📞 <b>Поддержка:</b>
• Telegram: @ai_support_bot
• Email: support@aibot.ru
• Время работы: 24/7

🔒 <b>Безопасность:</b>
Все платежи защищены по стандарту PCI DSS
"""
    
    from src.bot.keyboards.main import get_back_keyboard
    keyboard = get_back_keyboard()
    
    await callback.message.edit_text(help_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "statistics")
async def statistics_handler(callback: CallbackQuery, user: dict):
    """Показ статистики пользователя"""
    try:
        # Получаем статистику генераций
        from src.database.crud import GenerationCRUD
        generation_crud = GenerationCRUD()
        
        user_generations = await generation_crud.get_user_generations(
            user['telegram_id'], 
            limit=5
        )
        
        stats_text = f"""
📊 <b>Ваша статистика</b>

👤 <b>{user['full_name']}</b>
🆔 ID: <code>{user['telegram_id']}</code>

📈 <b>Общая статистика:</b>
• Изображений создано: {user['total_generations']}
• Потрачено средств: {user['total_spent']}₽
• Дней с нами: {(user.get('last_activity', user['created_at']) - user['created_at']).days}

💰 <b>Текущий статус:</b>
• Баланс: {user['balance']} изображений
• Подписка: {user.get('subscription_type', 'Нет').upper()}

🎨 <b>Последние генерации:</b>
"""
        
        # Добавляем информацию о последних генерациях
        if user_generations:
            for i, gen in enumerate(user_generations, 1):
                status_emoji = {
                    "completed": "✅",
                    "failed": "❌",
                    "processing": "⏳",
                    "pending": "🕐"
                }.get(gen.status, "❓")
                
                prompt_preview = gen.prompt[:30] + "..." if len(gen.prompt) > 30 else gen.prompt
                date_str = gen.created_at.strftime('%d.%m %H:%M')
                
                stats_text += f"{i}. {status_emoji} {prompt_preview} ({date_str})\n"
        else:
            stats_text += "Пока нет созданных изображений"
        
        from src.bot.keyboards.main import get_back_keyboard
        keyboard = get_back_keyboard()
        
        await callback.message.edit_text(stats_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в statistics_handler: {e}")
        await callback.answer("Произошла ошибка при загрузке статистики", show_alert=True)