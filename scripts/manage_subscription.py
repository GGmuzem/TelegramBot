"""
Скрипт для управления подписками пользователей
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone

# Добавляем корневую директорию в path
sys.path.insert(0, '.')

from src.database.connection import get_session
from src.database.models import User


async def add_subscription(telegram_id: int, subscription_type: str, days: int = 30):
    """
    Добавить подписку пользователю
    
    Args:
        telegram_id: Telegram ID пользователя
        subscription_type: Тип подписки (premium, pro)
        days: Количество дней подписки
    """
    try:
        async with get_session() as session:
            # Получаем пользователя
            user = await session.get(User, telegram_id)
            
            if not user:
                print(f"❌ Пользователь {telegram_id} не найден")
                return False
            
            # Устанавливаем подписку
            user.subscription_type = subscription_type
            user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=days)
            
            await session.commit()
            
            print(f"✅ Подписка успешно добавлена!")
            print(f"   Пользователь: {user.username or user.full_name} ({telegram_id})")
            print(f"   Тип: {subscription_type}")
            print(f"   Истекает: {user.subscription_expires_at.strftime('%d.%m.%Y %H:%M')}")
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def remove_subscription(telegram_id: int):
    """Убрать подписку у пользователя"""
    try:
        async with get_session() as session:
            user = await session.get(User, telegram_id)
            
            if not user:
                print(f"❌ Пользователь {telegram_id} не найден")
                return False
            
            user.subscription_type = None
            user.subscription_expires_at = None
            
            await session.commit()
            
            print(f"✅ Подписка удалена у {user.username or user.full_name}")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def check_subscription(telegram_id: int):
    """Проверить подписку пользователя"""
    try:
        async with get_session() as session:
            user = await session.get(User, telegram_id)
            
            if not user:
                print(f"❌ Пользователь {telegram_id} не найден")
                return
            
            print(f"\n📊 Информация о пользователе:")
            print(f"   ID: {user.telegram_id}")
            print(f"   Имя: {user.username or user.full_name}")
            print(f"   Баланс: {user.balance} изображений")
            
            if user.subscription_type:
                is_active = user.subscription_expires_at > datetime.now(timezone.utc) if user.subscription_expires_at else False
                status = "✅ Активна" if is_active else "❌ Истекла"
                
                print(f"   Подписка: {user.subscription_type} ({status})")
                if user.subscription_expires_at:
                    print(f"   Истекает: {user.subscription_expires_at.strftime('%d.%m.%Y %H:%M')}")
            else:
                print(f"   Подписка: Нет")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")


async def list_all_subscriptions():
    """Список всех активных подписок"""
    try:
        from sqlalchemy import select
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.subscription_type.isnot(None))
            )
            users = result.scalars().all()
            
            if not users:
                print("❌ Нет пользователей с подписками")
                return
            
            print(f"\n📋 Пользователи с подписками ({len(users)}):\n")
            
            for user in users:
                is_active = user.subscription_expires_at > datetime.now(timezone.utc) if user.subscription_expires_at else False
                status = "✅" if is_active else "❌"
                
                print(f"{status} {user.telegram_id} | @{user.username or 'NO_USERNAME'} | {user.subscription_type}")
                if user.subscription_expires_at:
                    print(f"   Истекает: {user.subscription_expires_at.strftime('%d.%m.%Y %H:%M')}")
                print()
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")


async def main():
    """Главная функция"""
    from src.database.connection import init_database
    
    # Инициализируем БД
    await init_database()
    
    if len(sys.argv) < 2:
        print("""
╔══════════════════════════════════════════════════════════╗
║       Управление подписками Telegram Bot                ║
╚══════════════════════════════════════════════════════════╝

Использование:

  1. Добавить подписку:
     python scripts/manage_subscription.py add <telegram_id> <type> [days]
     
     Пример: python scripts/manage_subscription.py add 5066402244 premium 30
     
     Типы подписок:
       - premium  (768x768, приоритет)
       - pro      (1024x1024, высший приоритет)
  
  2. Убрать подписку:
     python scripts/manage_subscription.py remove <telegram_id>
  
  3. Проверить подписку:
     python scripts/manage_subscription.py check <telegram_id>
  
  4. Список всех подписок:
     python scripts/manage_subscription.py list

Примеры:
  python scripts/manage_subscription.py add 5066402244 premium 30
  python scripts/manage_subscription.py check 5066402244
  python scripts/manage_subscription.py list
        """)
        return
    
    command = sys.argv[1]
    
    if command == "add":
        if len(sys.argv) < 4:
            print("❌ Использование: add <telegram_id> <type> [days]")
            return
        
        telegram_id = int(sys.argv[2])
        sub_type = sys.argv[3]
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        
        if sub_type not in ["premium", "pro"]:
            print("❌ Тип подписки должен быть 'premium' или 'pro'")
            return
        
        await add_subscription(telegram_id, sub_type, days)
    
    elif command == "remove":
        if len(sys.argv) < 3:
            print("❌ Использование: remove <telegram_id>")
            return
        
        telegram_id = int(sys.argv[2])
        await remove_subscription(telegram_id)
    
    elif command == "check":
        if len(sys.argv) < 3:
            print("❌ Использование: check <telegram_id>")
            return
        
        telegram_id = int(sys.argv[2])
        await check_subscription(telegram_id)
    
    elif command == "list":
        await list_all_subscriptions()
    
    else:
        print(f"❌ Неизвестная команда: {command}")
        print("Доступные команды: add, remove, check, list")


if __name__ == "__main__":
    asyncio.run(main())
