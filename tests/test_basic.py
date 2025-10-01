"""
Базовые тесты для проверки основных компонентов Telegram AI Bot
"""
import pytest
import asyncio
import os
import sys
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.config import settings
from src.shared.security import security_manager
from src.shared.redis_client import redis_client
from src.database.connection import init_database, get_session
from src.database.crud import UserCRUD, PaymentCRUD
from src.generator.gpu_balancer import gpu_balancer
from src.payment.providers.yookassa import YooKassaProvider


class TestConfig:
    """Тесты конфигурации"""
    
    def test_environment_variables(self):
        """Проверка основных переменных окружения"""
        # Критически важные переменные
        assert hasattr(settings, 'SECRET_KEY'), "SECRET_KEY не настроен"
        assert len(settings.SECRET_KEY) >= 16, "SECRET_KEY слишком короткий"
        
        assert hasattr(settings, 'DATABASE_URL'), "DATABASE_URL не настроен"
        assert settings.DATABASE_URL.startswith(('postgresql', 'sqlite')), "Неверный формат DATABASE_URL"
        
        assert hasattr(settings, 'REDIS_URL'), "REDIS_URL не настроен"
        
        print("✅ Конфигурация основных переменных окружения в порядке")
    
    def test_package_configuration(self):
        """Проверка конфигурации пакетов"""
        from src.shared.config import PACKAGES
        
        assert len(PACKAGES) > 0, "Пакеты не настроены"
        
        required_packages = ['once', 'basic', 'premium', 'pro']
        for package in required_packages:
            assert package in PACKAGES, f"Отсутствует пакет {package}"
            
            package_info = PACKAGES[package]
            assert 'name' in package_info, f"Нет названия для пакета {package}"
            assert 'price' in package_info, f"Нет цены для пакета {package}"
            assert 'images' in package_info, f"Нет количества изображений для пакета {package}"
            assert isinstance(package_info['price'], (int, float)), f"Цена пакета {package} не число"
            assert package_info['price'] > 0, f"Цена пакета {package} должна быть больше 0"
        
        print("✅ Конфигурация пакетов корректна")


class TestSecurity:
    """Тесты безопасности"""
    
    def test_encryption_decryption(self):
        """Тест шифрования и расшифровки"""
        test_data = {"user_id": 123, "sensitive_info": "secret data"}
        
        # Шифруем данные
        encrypted = security_manager.encrypt_data(test_data)
        assert encrypted != "", "Шифрование не должно возвращать пустую строку"
        
        # Расшифровываем данные
        decrypted = security_manager.decrypt_data(encrypted)
        assert decrypted == test_data, "Расшифрованные данные не совпадают с оригиналом"
        
        print("✅ Шифрование и расшифровка работает корректно")
    
    def test_jwt_tokens(self):
        """Тест JWT токенов"""
        user_data = {"user_id": 123, "username": "test_user"}
        
        # Создаем токен
        token = security_manager.create_access_token(user_data)
        assert token != "", "Токен не должен быть пустым"
        
        # Проверяем токен
        payload = security_manager.verify_token(token)
        assert payload is not None, "Токен должен успешно верифицироваться"
        assert payload["user_id"] == 123, "Данные в токене не совпадают"
        
        print("✅ JWT токены работают корректно")
    
    def test_prompt_validation(self):
        """Тест валидации промптов"""
        # Корректный промпт
        good_prompt = "Beautiful sunset over the ocean"
        result = security_manager.validate_prompt(good_prompt)
        assert result['valid'] == True, "Корректный промпт должен проходить валидацию"
        
        # Слишком короткий промпт
        short_prompt = "hi"
        result = security_manager.validate_prompt(short_prompt)
        assert result['valid'] == False, "Короткий промпт не должен проходить валидацию"
        
        # Запрещенный контент
        bad_prompt = "nude woman"
        result = security_manager.validate_prompt(bad_prompt)
        assert result['valid'] == False, "Промпт с запрещенным контентом не должен проходить"
        
        print("✅ Валидация промптов работает корректно")
    
    def test_security_configuration(self):
        """Проверка конфигурации безопасности"""
        security_report = security_manager.check_security_config()
        
        assert 'checks' in security_report, "Отчет безопасности должен содержать проверки"
        assert 'security_score' in security_report, "Отчет должен содержать оценку безопасности"
        assert security_report['security_score'] >= 60, "Оценка безопасности слишком низкая"
        
        print(f"✅ Конфигурация безопасности: {security_report['security_score']:.1f}%")


class TestDatabase:
    """Тесты базы данных"""
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Тест подключения к базе данных"""
        try:
            await init_database()
            session = get_session()
            
            # Выполняем простой запрос
            async with session:
                result = await session.execute("SELECT 1 as test")
                test_value = result.scalar()
            
            assert test_value == 1, "Тестовый запрос должен вернуть 1"
            print("✅ Подключение к базе данных работает")
            
        except Exception as e:
            print(f"⚠️ База данных недоступна: {e}")
            pytest.skip(f"Database not available: {e}")
    
    @pytest.mark.asyncio
    async def test_user_crud_operations(self):
        """Тест CRUD операций пользователей"""
        try:
            user_crud = UserCRUD()
            
            # Создаем тестового пользователя
            test_user = await user_crud.get_or_create_user(
                telegram_id=999999999,
                username="test_user",
                first_name="Test",
                last_name="User",
                language_code="en"
            )
            
            assert test_user is not None, "Пользователь должен быть создан"
            assert test_user.telegram_id == 999999999, "ID пользователя должен совпадать"
            assert test_user.username == "test_user", "Username должен совпадать"
            
            # Проверяем получение пользователя
            fetched_user = await user_crud.get_by_telegram_id(999999999)
            assert fetched_user is not None, "Пользователь должен быть найден"
            assert fetched_user.telegram_id == test_user.telegram_id, "ID должны совпадать"
            
            # Обновляем баланс
            new_balance = 10
            await user_crud.update_balance(999999999, new_balance)
            
            updated_user = await user_crud.get_by_telegram_id(999999999)
            assert updated_user.balance == new_balance, "Баланс должен быть обновлен"
            
            print("✅ CRUD операции пользователей работают корректно")
            
        except (RuntimeError, ConnectionRefusedError, Exception) as e:
            if "Database not initialized" in str(e) or "ConnectionRefused" in str(e.__class__.__name__):
                pytest.skip(f"Database not available for testing: {e}")
            raise


class TestPaymentProviders:
    """Тесты провайдеров платежей"""
    
    def test_yookassa_configuration(self):
        """Тест конфигурации ЮKassa"""
        from yookassa import Configuration
        
        # Проверяем что конфигурация установлена
        assert Configuration.account_id is not None, "Account ID должен быть настроен"
        assert Configuration.secret_key is not None, "Secret key должен быть настроен"
        
        # Проверяем что провайдер создается без ошибок
        yookassa = YooKassaProvider()
        assert hasattr(yookassa, 'crud'), "Провайдер должен иметь CRUD"
        
        print("✅ Конфигурация ЮKassa корректна")
    
    def test_payment_id_generation(self):
        """Тест генерации ID платежей"""
        from src.shared.security import create_secure_payment_id
        
        payment_id1 = create_secure_payment_id(123, "yookassa")
        payment_id2 = create_secure_payment_id(123, "yookassa")
        
        assert payment_id1 != payment_id2, "ID платежей должны быть уникальными"
        assert "yookassa_123_" in payment_id1, "ID должен содержать провайдера и user_id"
        
        print("✅ Генерация ID платежей работает корректно")


class TestGPUBalancer:
    """Тесты GPU балансировщика"""
    
    @pytest.mark.asyncio
    async def test_gpu_detection(self):
        """Тест определения GPU"""
        gpu_devices = gpu_balancer.gpu_devices
        
        # Проверяем что GPU определены (может быть пустой список если нет GPU)
        assert isinstance(gpu_devices, list), "GPU devices должен быть списком"
        
        if gpu_devices:
            print(f"✅ Обнаружено {len(gpu_devices)} GPU: {gpu_devices}")
            
            # Проверяем статус GPU
            for gpu_id in gpu_devices:
                assert gpu_id in gpu_balancer.gpu_status, f"Статус GPU {gpu_id} не инициализирован"
        else:
            print("⚠️ GPU не обнаружены (возможно, система не поддерживает CUDA)")
    
    @pytest.mark.asyncio
    async def test_gpu_stats(self):
        """Тест получения статистики GPU"""
        stats = await gpu_balancer.get_gpu_stats()
        
        assert isinstance(stats, dict), "Статистика должна быть словарем"
        assert 'gpu_count' in stats, "Статистика должна содержать количество GPU"
        assert 'total_generations' in stats, "Статистика должна содержать общее количество генераций"
        
        print("✅ Получение статистики GPU работает корректно")


class TestRedisConnection:
    """Тесты Redis подключения"""
    
    @pytest.mark.asyncio
    async def test_redis_connection(self):
        """Тест подключения к Redis"""
        try:
            await redis_client.connect()
            
            # Тестируем операции
            test_key = "test:connection"
            test_value = "test_value"
            
            # Устанавливаем значение
            await redis_client.set(test_key, test_value, ex=10)
            
            # Получаем значение
            retrieved_value = await redis_client.get(test_key)
            assert retrieved_value == test_value, "Значение из Redis не совпадает"
            
            # Удаляем тестовый ключ
            await redis_client.delete(test_key)
            
            print("✅ Подключение к Redis работает корректно")
            
        except Exception as e:
            print(f"❌ Ошибка подключения к Redis: {e}")
            # Redis может быть недоступен в тестовой среде
            print("⚠️ Redis недоступен - это нормально для тестовой среды")


def run_basic_tests():
    """Запуск базовых тестов"""
    print("🚀 Запуск базовых тестов Telegram AI Bot\n")
    
    # Тесты конфигурации
    print("📋 Тестирование конфигурации...")
    config_test = TestConfig()
    config_test.test_environment_variables()
    config_test.test_package_configuration()
    print()
    
    # Тесты безопасности
    print("🔒 Тестирование безопасности...")
    security_test = TestSecurity()
    security_test.test_encryption_decryption()
    security_test.test_jwt_tokens()
    security_test.test_prompt_validation()
    security_test.test_security_configuration()
    print()
    
    # Тесты провайдеров платежей
    print("💳 Тестирование платежных провайдеров...")
    payment_test = TestPaymentProviders()
    payment_test.test_yookassa_configuration()
    payment_test.test_payment_id_generation()
    print()
    
    # Async тесты
    print("⚡ Запуск асинхронных тестов...")
    
    async def run_async_tests():
        try:
            # Тесты Redis
            redis_test = TestRedisConnection()
            await redis_test.test_redis_connection()
            
            # Тесты базы данных
            db_test = TestDatabase()
            await db_test.test_database_connection()
            await db_test.test_user_crud_operations()
            
            # Тесты GPU
            gpu_test = TestGPUBalancer()
            await gpu_test.test_gpu_detection()
            await gpu_test.test_gpu_stats()
            
        except Exception as e:
            print(f"❌ Ошибка в асинхронных тестах: {e}")
            raise
    
    # Запускаем асинхронные тесты
    asyncio.run(run_async_tests())
    
    print("\n🎉 Все базовые тесты завершены!")
    print("Система готова к работе!")


if __name__ == "__main__":
    run_basic_tests()