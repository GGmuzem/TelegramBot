"""
Модуль безопасности для Telegram AI Bot
Обеспечивает шифрование, JWT токены, валидацию и защиту
"""
import secrets
import hashlib
import hmac
import base64
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
import re
import json

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from src.shared.config import settings

logger = logging.getLogger(__name__)


class SecurityManager:
    """Центральный менеджер безопасности"""
    
    def __init__(self):
        # Контекст для хеширования паролей
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12
        )
        
        # Ключ шифрования (генерируется из SECRET_KEY)
        self.encryption_key = self._derive_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # JWT настройки
        self.jwt_secret = settings.SECRET_KEY
        self.jwt_algorithm = "HS256"
        self.jwt_access_token_expire = timedelta(hours=24)
        self.jwt_refresh_token_expire = timedelta(days=7)
    
    def _derive_encryption_key(self) -> bytes:
        """Генерация ключа шифрования из SECRET_KEY"""
        key_data = settings.SECRET_KEY.encode('utf-8')
        # Используем PBKDF2 для генерации 32-байтного ключа
        derived_key = hashlib.pbkdf2_hmac('sha256', key_data, b'salt', 100000)
        return base64.urlsafe_b64encode(derived_key)
    
    # === JWT токены ===
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Создание JWT access токена"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + self.jwt_access_token_expire
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.jwt_secret,
            algorithm=self.jwt_algorithm
        )
        
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Создание JWT refresh токена"""
        to_encode = data.copy()
        expire = datetime.utcnow() + self.jwt_refresh_token_expire
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.jwt_secret,
            algorithm=self.jwt_algorithm
        )
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Верификация JWT токена"""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT токен истек")
            return None
        except jwt.JWTError as e:
            logger.warning(f"Ошибка верификации JWT токена: {e}")
            return None
    
    # === Шифрование данных ===
    
    def encrypt_data(self, data: Union[str, Dict[str, Any]]) -> str:
        """Шифрование данных"""
        try:
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False)
            
            encrypted_data = self.cipher.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            return ""
    
    def decrypt_data(self, encrypted_data: str) -> Optional[Union[str, Dict[str, Any]]]:
        """Расшифровка данных"""
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.cipher.decrypt(decoded_data).decode('utf-8')
            
            # Пытаемся распарсить как JSON
            try:
                return json.loads(decrypted_data)
            except json.JSONDecodeError:
                return decrypted_data
        except Exception as e:
            logger.error(f"Ошибка расшифровки: {e}")
            return None
    
    # === Хеширование паролей ===
    
    def hash_password(self, password: str) -> str:
        """Хеширование пароля"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверка пароля"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    # === Подписи webhook ===
    
    def create_webhook_signature(self, data: str, secret: str) -> str:
        """Создание подписи для webhook"""
        signature = hmac.new(
            secret.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_webhook_signature(
        self,
        data: str,
        signature: str,
        secret: str,
        signature_header: str = "sha256"
    ) -> bool:
        """Проверка подписи webhook"""
        try:
            expected_signature = self.create_webhook_signature(data, secret)
            
            # Удаляем префикс если есть (например, "sha256=")
            if signature_header in signature:
                signature = signature.split("=", 1)[1]
            
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Ошибка проверки подписи webhook: {e}")
            return False
    
    # === Генерация случайных данных ===
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Генерация криптографически стойкого токена"""
        return secrets.token_urlsafe(length)
    
    def generate_api_key(self) -> str:
        """Генерация API ключа"""
        return f"ai_bot_{secrets.token_urlsafe(32)}"
    
    def generate_payment_id(self, user_id: int, provider: str = "yookassa") -> str:
        """Генерация уникального ID платежа"""
        timestamp = int(datetime.utcnow().timestamp())
        random_part = secrets.token_hex(4)
        return f"{provider}_{user_id}_{timestamp}_{random_part}"
    
    # === Валидация данных ===
    
    def validate_telegram_data(self, data: Dict[str, Any]) -> bool:
        """Валидация данных от Telegram"""
        required_fields = ['id', 'first_name']
        
        # Проверяем обязательные поля
        for field in required_fields:
            if field not in data:
                logger.warning(f"Отсутствует поле {field} в данных Telegram")
                return False
        
        # Проверяем типы данных
        if not isinstance(data.get('id'), int):
            logger.warning("ID пользователя должен быть числом")
            return False
        
        # Проверяем длину имени
        first_name = data.get('first_name', '')
        if not (1 <= len(first_name) <= 100):
            logger.warning("Некорректная длина имени")
            return False
        
        # Проверяем username если есть
        username = data.get('username', '')
        if username and not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
            logger.warning("Некорректный формат username")
            return False
        
        return True
    
    def validate_payment_data(self, data: Dict[str, Any]) -> bool:
        """Валидация платежных данных"""
        try:
            # Проверяем обязательные поля
            required_fields = ['user_id', 'amount', 'package']
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Отсутствует поле {field} в платежных данных")
                    return False
            
            # Проверяем типы и значения
            user_id = data.get('user_id')
            if not isinstance(user_id, int) or user_id <= 0:
                logger.warning("Некорректный user_id")
                return False
            
            amount = data.get('amount')
            try:
                amount = float(amount)
                if amount <= 0 or amount > 100000:  # Максимум 100,000₽
                    logger.warning(f"Некорректная сумма платежа: {amount}")
                    return False
            except (ValueError, TypeError):
                logger.warning("Сумма платежа должна быть числом")
                return False
            
            # Проверяем пакет
            package = data.get('package')
            from src.shared.config import PACKAGES
            if package not in PACKAGES:
                logger.warning(f"Неизвестный пакет: {package}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка валидации платежных данных: {e}")
            return False
    
    def sanitize_text(self, text: str, max_length: int = 1000) -> str:
        """Очистка текста от вредоносного содержимого"""
        if not isinstance(text, str):
            return ""
        
        # Обрезаем длину
        text = text[:max_length]
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Удаляем управляющие символы кроме переносов строк
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Нормализуем пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def validate_prompt(self, prompt: str) -> Dict[str, Any]:
        """Валидация промпта для AI генерации"""
        result = {
            'valid': True,
            'sanitized_prompt': '',
            'warnings': [],
            'blocked_reasons': []
        }
        
        # Базовые проверки
        if not prompt or len(prompt.strip()) < 3:
            result['valid'] = False
            result['blocked_reasons'].append('Слишком короткий промпт')
            return result
        
        if len(prompt) > 1000:
            result['warnings'].append('Промпт обрезан до 1000 символов')
            prompt = prompt[:1000]
        
        # Очищаем текст
        sanitized = self.sanitize_text(prompt)
        
        # Проверяем на запрещенный контент
        forbidden_keywords = [
            # NSFW контент
            'nude', 'naked', 'porn', 'sex', 'explicit',
            # Насилие
            'blood', 'violence', 'kill', 'murder', 'weapon', 'gun',
            # Другие ограничения
            'nazi', 'hitler', 'drugs', 'cocaine'
        ]
        
        prompt_lower = sanitized.lower()
        for keyword in forbidden_keywords:
            if keyword in prompt_lower:
                result['valid'] = False
                result['blocked_reasons'].append(f'Запрещенное содержимое: {keyword}')
        
        result['sanitized_prompt'] = sanitized
        return result
    
    # === Безопасность API ===
    
    def create_rate_limit_key(self, identifier: str, action: str) -> str:
        """Создание ключа для rate limiting"""
        return f"rate_limit:{action}:{identifier}"
    
    def hash_sensitive_data(self, data: str) -> str:
        """Хеширование чувствительных данных для логирования"""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
    
    def mask_card_number(self, card_number: str) -> str:
        """Маскировка номера карты"""
        if not card_number or len(card_number) < 8:
            return "****"
        
        return f"{card_number[:4]}****{card_number[-4:]}"
    
    def mask_email(self, email: str) -> str:
        """Маскировка email адреса"""
        if not email or '@' not in email:
            return "****@****.***"
        
        local, domain = email.split('@', 1)
        
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        
        domain_parts = domain.split('.')
        if len(domain_parts) >= 2:
            masked_domain = "*" * len(domain_parts[0]) + "." + domain_parts[-1]
        else:
            masked_domain = "*" * len(domain)
        
        return f"{masked_local}@{masked_domain}"
    
    # === Проверка безопасности системы ===
    
    def check_security_config(self) -> Dict[str, Any]:
        """Проверка конфигурации безопасности"""
        checks = {
            'secret_key_strong': len(settings.SECRET_KEY) >= 32,
            'jwt_configured': bool(self.jwt_secret),
            'encryption_ready': bool(self.encryption_key),
            'webhook_secrets_set': bool(
                getattr(settings, 'WEBHOOK_SECRET', '') and
                getattr(settings, 'YOOKASSA_SECRET_KEY', '')
            ),
            'https_required': settings.ENVIRONMENT == 'production',
            'debug_disabled': not settings.DEBUG or settings.ENVIRONMENT != 'production'
        }
        
        warnings = []
        errors = []
        
        if not checks['secret_key_strong']:
            errors.append('SECRET_KEY слишком короткий (минимум 32 символа)')
        
        if not checks['webhook_secrets_set']:
            warnings.append('Не все webhook секреты настроены')
        
        if settings.DEBUG and settings.ENVIRONMENT == 'production':
            errors.append('DEBUG режим включен в продакшене')
        
        return {
            'checks': checks,
            'warnings': warnings,
            'errors': errors,
            'security_score': sum(checks.values()) / len(checks) * 100
        }
    
    # === Логирование безопасности ===
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info"
    ):
        """Логирование событий безопасности"""
        event_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'details': details or {},
            'severity': severity
        }
        
        log_message = f"Security event: {event_type}"
        if user_id:
            log_message += f" (user: {user_id})"
        
        if severity == "error":
            logger.error(log_message, extra=event_data)
        elif severity == "warning":
            logger.warning(log_message, extra=event_data)
        else:
            logger.info(log_message, extra=event_data)


# Глобальный экземпляр менеджера безопасности
security_manager = SecurityManager()


# Утилитарные функции
def create_secure_payment_id(user_id: int, provider: str = "yookassa") -> str:
    """Создание безопасного ID платежа"""
    return security_manager.generate_payment_id(user_id, provider)


def validate_and_sanitize_prompt(prompt: str) -> Dict[str, Any]:
    """Валидация и очистка промпта"""
    return security_manager.validate_prompt(prompt)


def encrypt_sensitive_data(data: Union[str, Dict[str, Any]]) -> str:
    """Шифрование чувствительных данных"""
    return security_manager.encrypt_data(data)


def decrypt_sensitive_data(encrypted_data: str) -> Optional[Union[str, Dict[str, Any]]]:
    """Расшифровка чувствительных данных"""
    return security_manager.decrypt_data(encrypted_data)


def verify_telegram_webhook(data: str, signature: str) -> bool:
    """Проверка подписи Telegram webhook"""
    webhook_secret = getattr(settings, 'WEBHOOK_SECRET', '')
    return security_manager.verify_webhook_signature(data, signature, webhook_secret)


def create_jwt_tokens(user_data: Dict[str, Any]) -> Dict[str, str]:
    """Создание пары JWT токенов"""
    return {
        'access_token': security_manager.create_access_token(user_data),
        'refresh_token': security_manager.create_refresh_token(user_data)
    }