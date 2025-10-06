"""
Подключение к базе данных и инициализация
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from src.shared.config import settings
from src.database.models import Base

logger = logging.getLogger(__name__)

# Глобальные переменные для движка и сессий
engine = None
async_session = None


async def init_database():
    """Инициализация подключения к базе данных"""
    global engine, async_session
    
    try:
        # Создаем движок базы данных
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            future=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=3600,  # 1 час
            connect_args={
                "command_timeout": 60,
                "server_settings": {
                    "application_name": "telegram_ai_bot",
                    "jit": "off"
                }
            }
        )
        
        # Создаем фабрику сессий
        async_session = sessionmaker(
            engine, 
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Создаем таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ База данных инициализирована успешно")
        
        # Проверяем подключение
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            logger.info("✅ Подключение к базе данных проверено")
        
        # Инициализируем тарифы по умолчанию
        await _init_default_tariffs()
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise


async def _init_default_tariffs():
    """Создание тарифов по умолчанию если их нет"""
    from src.database.models import Tariff
    from decimal import Decimal
    
    try:
        async with get_session() as session:
            # Проверяем есть ли тарифы
            result = await session.execute(text("SELECT COUNT(*) FROM tariffs"))
            count = result.scalar()
            
            if count == 0:
                logger.info("Создаю тарифы по умолчанию...")
                
                default_tariffs = [
                    Tariff(
                        name="Базовый",
                        price=Decimal("100.00"),
                        generations=10,
                        image_size="512x512",
                        priority=False,
                        is_active=True
                    ),
                    Tariff(
                        name="Стандарт",
                        price=Decimal("300.00"),
                        generations=35,
                        image_size="768x768",
                        priority=False,
                        is_active=True
                    ),
                    Tariff(
                        name="Премиум",
                        price=Decimal("500.00"),
                        generations=65,
                        image_size="1024x1024",
                        priority=True,
                        is_active=True
                    ),
                    Tariff(
                        name="Профи",
                        price=Decimal("1000.00"),
                        generations=150,
                        image_size="1024x1024",
                        priority=True,
                        is_active=True
                    )
                ]
                
                for tariff in default_tariffs:
                    session.add(tariff)
                
                await session.commit()
                logger.info(f"✅ Создано {len(default_tariffs)} тарифов по умолчанию")
            else:
                logger.info(f"Тарифы уже существуют ({count} шт.)")
                
    except Exception as e:
        logger.error(f"Ошибка при создании тарифов: {e}")


async def close_database():
    """Закрытие подключения к базе данных"""
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("🔌 Подключение к базе данных закрыто")


def get_session() -> AsyncSession:
    """Получение сессии базы данных"""
    if not async_session:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    return async_session()


async def health_check() -> bool:
    """Проверка работоспособности базы данных"""
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1 as health"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
    
    async def initialize(self):
        """Инициализация менеджера"""
        await init_database()
        self.engine = engine
        self.session_factory = async_session
    
    async def close(self):
        """Закрытие менеджера"""
        await close_database()
    
    async def create_session(self) -> AsyncSession:
        """Создание новой сессии"""
        if not self.session_factory:
            await self.initialize()
        return self.session_factory()
    
    async def execute_transaction(self, operations):
        """Выполнение транзакции"""
        async with self.create_session() as session:
            try:
                async with session.begin():
                    result = await operations(session)
                    return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Transaction failed: {e}")
                raise
    
    async def get_database_info(self):
        """Получение информации о базе данных"""
        try:
            async with self.create_session() as session:
                # Версия PostgreSQL
                result = await session.execute(text("SELECT version()"))
                version = result.scalar()
                
                # Размер базы данных
                result = await session.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                )
                size = result.scalar()
                
                # Количество подключений
                result = await session.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                )
                connections = result.scalar()
                
                return {
                    "version": version,
                    "size": size,
                    "connections": connections,
                    "status": "healthy"
                }
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"status": "error", "error": str(e)}


# Глобальный экземпляр менеджера
db_manager = DatabaseManager()


# Context manager для автоматического управления сессиями
class DatabaseSession:
    """Context manager для работы с сессиями базы данных"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self) -> AsyncSession:
        self.session = get_session()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
            await self.session.close()


# Декоратор для автоматической обработки сессий
def with_database_session(func):
    """Декоратор для автоматической обработки сессий БД"""
    async def wrapper(*args, **kwargs):
        async with DatabaseSession() as session:
            return await func(*args, session=session, **kwargs)
    return wrapper


# Функции для миграций
async def create_migration_table():
    """Создание таблицы миграций"""
    async with get_session() as session:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await session.commit()


async def apply_migration(migration_name: str, migration_sql: str):
    """Применение миграции"""
    async with get_session() as session:
        # Проверяем, была ли миграция уже применена
        result = await session.execute(
            text("SELECT id FROM migrations WHERE name = :name"),
            {"name": migration_name}
        )
        
        if result.scalar():
            logger.info(f"Migration {migration_name} already applied")
            return
        
        try:
            # Выполняем миграцию
            await session.execute(text(migration_sql))
            
            # Записываем в таблицу миграций
            await session.execute(
                text("INSERT INTO migrations (name) VALUES (:name)"),
                {"name": migration_name}
            )
            
            await session.commit()
            logger.info(f"✅ Migration {migration_name} applied successfully")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Failed to apply migration {migration_name}: {e}")
            raise


async def get_applied_migrations():
    """Получение списка примененных миграций"""
    try:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT name, applied_at FROM migrations ORDER BY applied_at")
            )
            return result.fetchall()
    except Exception as e:
        logger.error(f"Failed to get migrations: {e}")
        return []


# Функции для бекапа и восстановления
async def backup_database(backup_path: str):
    """Создание бекапа базы данных"""
    import subprocess
    import os
    
    try:
        # Извлекаем параметры подключения из URL
        from urllib.parse import urlparse
        parsed = urlparse(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
        
        env = os.environ.copy()
        env['PGPASSWORD'] = parsed.password
        
        command = [
            'pg_dump',
            '-h', parsed.hostname,
            '-p', str(parsed.port or 5432),
            '-U', parsed.username,
            '-d', parsed.path[1:],  # Убираем начальный '/'
            '-f', backup_path,
            '--verbose',
            '--no-owner',
            '--no-privileges'
        ]
        
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ Database backup created: {backup_path}")
            return True
        else:
            logger.error(f"❌ Backup failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Backup error: {e}")
        return False


# Функции мониторинга производительности
async def get_database_stats():
    """Получение статистики базы данных"""
    try:
        async with get_session() as session:
            # Статистика таблиц
            tables_stats = await session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins,
                    n_tup_upd,
                    n_tup_del,
                    n_live_tup,
                    n_dead_tup
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
            """))
            
            # Статистика подключений
            connections_stats = await session.execute(text("""
                SELECT 
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) FILTER (WHERE state = 'idle') as idle_connections
                FROM pg_stat_activity 
                WHERE datname = current_database()
            """))
            
            # Размер базы данных
            db_size = await session.execute(text("""
                SELECT 
                    pg_size_pretty(pg_database_size(current_database())) as db_size,
                    pg_database_size(current_database()) as db_size_bytes
            """))
            
            return {
                "tables": tables_stats.fetchall(),
                "connections": connections_stats.fetchone(),
                "size": db_size.fetchone()
            }
            
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return None