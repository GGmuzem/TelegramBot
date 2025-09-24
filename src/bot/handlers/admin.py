"""
Админ панель для управления Telegram AI Bot
"""
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from src.bot.keyboards.main import get_admin_keyboard
from src.database.crud import UserCRUD, PaymentCRUD, GenerationCRUD
from src.generator.gpu_balancer import gpu_balancer
from src.generator.models_manager import model_manager
from src.shared.redis_client import redis_client
from src.shared.config import settings

logger = logging.getLogger(__name__)
router = Router()

# CRUD сервисы
user_crud = UserCRUD()
payment_crud = PaymentCRUD() 
generation_crud = GenerationCRUD()


def admin_required(func):
    """Декоратор для проверки админских прав"""
    async def wrapper(callback_or_message, user: dict, *args, **kwargs):
        if not user.get('is_admin', False):
            if hasattr(callback_or_message, 'answer'):
                await callback_or_message.answer("❌ Нет прав доступа", show_alert=True)
            else:
                await callback_or_message.answer("❌ Нет прав доступа к админ панели")
            return
        
        return await func(callback_or_message, user, *args, **kwargs)
    return wrapper


@router.message(Command("admin"))
@admin_required
async def admin_panel_handler(message: Message, user: dict):
    """Главное меню админ панели"""
    try:
        keyboard = get_admin_keyboard()
        
        admin_text = f"""
👑 <b>Админ панель</b>

👤 <b>Администратор:</b> {user['full_name']}
🆔 <b>ID:</b> <code>{user['telegram_id']}</code>
⏰ <b>Вход в систему:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

🎛️ <b>Доступные функции:</b>
• Статистика системы
• Управление пользователями  
• Финансовые отчеты
• Мониторинг генерации
• Логи системы
• Настройки конфигурации

Выберите раздел ⬇️
"""
        
        await message.answer(admin_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в admin_panel_handler: {e}")
        await message.answer("Ошибка загрузки админ панели")


@router.callback_query(F.data == "admin_stats")
@admin_required
async def admin_system_stats(callback: CallbackQuery, user: dict):
    """Системная статистика"""
    try:
        # Получаем общую статистику
        users_stats = await user_crud.get_users_statistics()
        payments_stats = await payment_crud.get_payments_statistics()
        generations_stats = await generation_crud.get_generations_statistics()
        gpu_stats = await gpu_balancer.get_gpu_stats()
        redis_stats = await redis_client.get_statistics()
        
        stats_text = f"""
📊 <b>Системная статистика</b>

👥 <b>Пользователи:</b>
• Всего: {users_stats.get('total_users', 0)}
• Активных сегодня: {users_stats.get('active_today', 0)}
• Новых за неделю: {users_stats.get('new_week', 0)}
• Премиум: {users_stats.get('premium_users', 0)}

💰 <b>Финансы:</b>
• Всего доходов: {payments_stats.get('total_revenue', 0)}₽
• Доходы сегодня: {payments_stats.get('revenue_today', 0)}₽
• Успешных платежей: {payments_stats.get('successful_payments', 0)}
• Средний чек: {payments_stats.get('average_payment', 0)}₽

🎨 <b>Генерации:</b>
• Всего изображений: {generations_stats.get('total_generations', 0)}
• Сегодня: {generations_stats.get('generations_today', 0)}
• В очереди: {generations_stats.get('queue_length', 0)}
• Среднее время: {generations_stats.get('avg_time', 0):.1f}с

🖥️ <b>GPU ({gpu_stats.get('gpu_count', 0)} шт.):</b>
• Доступно: {sum(1 for avail in gpu_stats.get('availability', {}).values() if avail)}
• В работе: {sum(1 for avail in gpu_stats.get('availability', {}).values() if not avail)}
• Среднее время генерации: {gpu_stats.get('average_generation_time', 0):.1f}с

🔄 <b>Redis:</b>
• Статус: {"✅ OK" if redis_stats.get('connected') else "❌ Error"}
• Использовано памяти: {redis_stats.get('memory_usage_mb', 0)} MB
• Активных соединений: {redis_stats.get('connected_clients', 0)}

🕐 <b>Обновлено:</b> {datetime.now().strftime('%H:%M:%S')}
"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="admin_stats"
            )],
            [InlineKeyboardButton(
                text="📈 Детальная аналитика",
                callback_data="admin_analytics"
            )],
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="admin_panel"
            )]
        ])
        
        await callback.message.edit_text(stats_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback.answer("Ошибка получения статистики", show_alert=True)


@router.callback_query(F.data == "admin_users")
@admin_required
async def admin_user_management(callback: CallbackQuery, user: dict):
    """Управление пользователями"""
    try:
        # Получаем топ пользователей
        top_users = await user_crud.get_top_users(limit=10)
        recent_users = await user_crud.get_recent_users(limit=5)
        
        users_text = f"""
👥 <b>Управление пользователями</b>

📊 <b>Топ по генерациям:</b>
"""
        
        for i, user_info in enumerate(top_users, 1):
            users_text += (
                f"{i}. {user_info.full_name} "
                f"({user_info.total_generations} генераций)\n"
            )
        
        users_text += f"""

👋 <b>Новые пользователи:</b>
"""
        
        for user_info in recent_users:
            reg_date = user_info.created_at.strftime('%d.%m %H:%M')
            users_text += (
                f"• {user_info.full_name} "
                f"(рег. {reg_date})\n"
            )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔍 Поиск пользователя",
                callback_data="admin_find_user"
            )],
            [InlineKeyboardButton(
                text="📊 Детальная статистика",
                callback_data="admin_user_stats"
            )],
            [InlineKeyboardButton(
                text="🚫 Заблокированные",
                callback_data="admin_blocked_users"
            )],
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="admin_panel"
            )]
        ])
        
        await callback.message.edit_text(users_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка управления пользователями: {e}")
        await callback.answer("Ошибка загрузки данных", show_alert=True)


@router.callback_query(F.data == "admin_finance")
@admin_required
async def admin_financial_reports(callback: CallbackQuery, user: dict):
    """Финансовые отчеты"""
    try:
        # Получаем финансовую статистику
        today_revenue = await payment_crud.get_revenue_by_period(days=1)
        week_revenue = await payment_crud.get_revenue_by_period(days=7)
        month_revenue = await payment_crud.get_revenue_by_period(days=30)
        
        # Статистика по пакетам
        package_stats = await payment_crud.get_package_statistics()
        
        # Конверсия
        conversion_stats = await payment_crud.get_conversion_statistics()
        
        finance_text = f"""
💰 <b>Финансовые отчеты</b>

📈 <b>Доходы:</b>
• Сегодня: {today_revenue}₽
• За неделю: {week_revenue}₽  
• За месяц: {month_revenue}₽

📦 <b>Популярные пакеты:</b>
"""
        
        for package, stats in package_stats.items():
            package_name = {
                'once': '💎 Разовая',
                'basic': '📦 Базовый',
                'premium': '⭐ Премиум', 
                'pro': '🔥 Профи'
            }.get(package, package)
            
            finance_text += (
                f"• {package_name}: {stats['count']} шт. "
                f"({stats['revenue']}₽)\n"
            )
        
        finance_text += f"""

📊 <b>Конверсия:</b>
• Регистрация → Покупка: {conversion_stats.get('reg_to_purchase', 0):.1f}%
• Просмотр → Оплата: {conversion_stats.get('view_to_payment', 0):.1f}%
• Средний LTV: {conversion_stats.get('average_ltv', 0)}₽

💳 <b>Способы оплаты:</b>
• Банковские карты: {conversion_stats.get('card_percentage', 0):.1f}%
• СБП: {conversion_stats.get('sbp_percentage', 0):.1f}%
• Другие: {conversion_stats.get('other_percentage', 0):.1f}%
"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📊 Экспорт отчета",
                callback_data="admin_export_finance"
            )],
            [InlineKeyboardButton(
                text="📈 График доходов",
                callback_data="admin_revenue_chart"
            )],
            [InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="admin_finance"
            )],
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="admin_panel"
            )]
        ])
        
        await callback.message.edit_text(finance_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка финансовых отчетов: {e}")
        await callback.answer("Ошибка загрузки отчетов", show_alert=True)


@router.callback_query(F.data == "admin_generation")
@admin_required  
async def admin_generation_monitoring(callback: CallbackQuery, user: dict):
    """Мониторинг генерации изображений"""
    try:
        # GPU статистика
        gpu_stats = await gpu_balancer.get_gpu_stats()
        model_info = model_manager.get_model_info()
        
        # Очередь генерации
        queue_stats = await redis_client.get_queue_statistics()
        
        generation_text = f"""
🎨 <b>Мониторинг генерации</b>

🖥️ <b>GPU Статус:</b>
"""
        
        for gpu_id, status in gpu_stats.get('gpu_status', {}).items():
            busy_status = "🔴 Занят" if status['busy'] else "🟢 Свободен"
            generation_text += (
                f"GPU {gpu_id}: {busy_status} "
                f"(Очередь: {status['queue_length']})\n"
            )
        
        generation_text += f"""

📊 <b>Статистика генерации:</b>
• Всего генераций: {gpu_stats.get('total_generations', 0)}
• Успешных: {gpu_stats.get('total_generations', 0) - gpu_stats.get('total_errors', 0)}
• Ошибок: {gpu_stats.get('total_errors', 0)}
• Среднее время: {gpu_stats.get('average_generation_time', 0):.1f}с

🔄 <b>Очереди:</b>
• Обычная очередь: {queue_stats.get('normal_queue', 0)}
• Приоритетная: {queue_stats.get('priority_queue', 0)}
• Обрабатывается: {queue_stats.get('processing', 0)}

🧠 <b>Модели:</b>
• Загружено GPU: {len(model_info.get('loaded_gpus', []))}
• Использование памяти: {sum(usage.get('allocated_gb', 0) for usage in model_info.get('memory_usage', {}).values()):.1f} GB
"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Перезагрузить модели",
                callback_data="admin_reload_models"
            )],
            [InlineKeyboardButton(
                text="🗑️ Очистить очереди",
                callback_data="admin_clear_queues"
            )],
            [InlineKeyboardButton(
                text="📊 GPU детали",
                callback_data="admin_gpu_details"
            )],
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="admin_panel"
            )]
        ])
        
        await callback.message.edit_text(generation_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка мониторинга генерации: {e}")
        await callback.answer("Ошибка загрузки мониторинга", show_alert=True)


@router.callback_query(F.data == "admin_logs")
@admin_required
async def admin_system_logs(callback: CallbackQuery, user: dict):
    """Просмотр системных логов"""
    try:
        # Получаем последние логи
        import subprocess
        import os
        
        logs_text = "📝 <b>Системные логи</b>\n\n"
        
        # Логи бота
        try:
            bot_logs = subprocess.run(
                ["tail", "-20", "logs/bot/bot.log"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            if bot_logs.returncode == 0:
                logs_text += "<b>🤖 Telegram Bot:</b>\n"
                logs_text += f"<code>{bot_logs.stdout[-1000:]}</code>\n\n"
        except:
            logs_text += "<b>🤖 Telegram Bot:</b> Логи недоступны\n\n"
        
        # Логи генератора
        try:
            gen_logs = subprocess.run(
                ["tail", "-10", "logs/generator/generator.log"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if gen_logs.returncode == 0:
                logs_text += "<b>🎨 AI Generator:</b>\n"
                logs_text += f"<code>{gen_logs.stdout[-500:]}</code>\n\n"
        except:
            logs_text += "<b>🎨 AI Generator:</b> Логи недоступны\n\n"
        
        # Логи платежей
        try:
            payment_logs = subprocess.run(
                ["tail", "-10", "logs/webhook/webhook.log"],
                capture_output=True, 
                text=True,
                timeout=5
            )
            if payment_logs.returncode == 0:
                logs_text += "<b>💳 Payment Webhook:</b>\n"
                logs_text += f"<code>{payment_logs.stdout[-500:]}</code>"
        except:
            logs_text += "<b>💳 Payment Webhook:</b> Логи недоступны"
        
        # Ограничиваем длину сообщения
        if len(logs_text) > 4000:
            logs_text = logs_text[:3900] + "\n\n... (обрезано)"
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📁 Скачать полные логи",
                callback_data="admin_download_logs"
            )],
            [InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="admin_logs"
            )],
            [InlineKeyboardButton(
                text="⚠️ Только ошибки",
                callback_data="admin_error_logs"
            )],
            [InlineKeyboardButton(
                text="◀️ Назад", 
                callback_data="admin_panel"
            )]
        ])
        
        await callback.message.edit_text(logs_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения логов: {e}")
        await callback.answer("Ошибка получения логов", show_alert=True)


@router.callback_query(F.data == "admin_reload_models")
@admin_required
async def admin_reload_models(callback: CallbackQuery, user: dict):
    """Перезагрузка AI моделей"""
    try:
        await callback.message.edit_text(
            "🔄 <b>Перезагрузка моделей...</b>\n\n"
            "⏳ Это может занять несколько минут..."
        )
        
        # Очищаем существующие модели
        await model_manager.cleanup_models()
        
        # Загружаем модели заново
        load_results = await model_manager.load_models_on_gpus()
        
        success_count = sum(1 for success in load_results.values() if success)
        total_count = len(load_results)
        
        result_text = f"""
✅ <b>Перезагрузка моделей завершена</b>

📊 <b>Результат:</b>
• Успешно: {success_count}/{total_count} GPU
• Время: {datetime.now().strftime('%H:%M:%S')}

🖥️ <b>GPU статус:</b>
"""
        
        for gpu_id, success in load_results.items():
            status = "✅ OK" if success else "❌ Ошибка"
            result_text += f"GPU {gpu_id}: {status}\n"
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад к мониторингу",
                callback_data="admin_generation"
            )]
        ])
        
        await callback.message.edit_text(result_text, reply_markup=keyboard)
        await callback.answer("Модели перезагружены!")
        
    except Exception as e:
        logger.error(f"Ошибка перезагрузки моделей: {e}")
        await callback.answer("Ошибка перезагрузки", show_alert=True)


@router.callback_query(F.data == "admin_clear_queues")
@admin_required 
async def admin_clear_queues(callback: CallbackQuery, user: dict):
    """Очистка очередей генерации"""
    try:
        # Очищаем очереди в Redis
        await redis_client.clear_generation_queues()
        
        result_text = f"""
✅ <b>Очереди очищены</b>

🔄 <b>Действия:</b>
• Обычная очередь: очищена
• Приоритетная очередь: очищена  
• Обрабатываемые задачи: сброшены

⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}

⚠️ <b>Внимание:</b>
Пользователи в очереди получат уведомление об отмене задач.
"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад к мониторингу",
                callback_data="admin_generation"
            )]
        ])
        
        await callback.message.edit_text(result_text, reply_markup=keyboard)
        await callback.answer("Очереди очищены!")
        
    except Exception as e:
        logger.error(f"Ошибка очистки очередей: {e}")
        await callback.answer("Ошибка очистки очередей", show_alert=True)


@router.callback_query(F.data == "admin_panel")
@admin_required
async def back_to_admin_panel(callback: CallbackQuery, user: dict):
    """Возврат в главное меню админ панели"""
    try:
        keyboard = get_admin_keyboard()
        
        admin_text = f"""
👑 <b>Админ панель</b>

👤 <b>Администратор:</b> {user['full_name']}
⏰ <b>Текущее время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

Выберите раздел ⬇️
"""
        
        await callback.message.edit_text(admin_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка возврата в админ панель: {e}")
        await callback.answer("Ошибка загрузки", show_alert=True)