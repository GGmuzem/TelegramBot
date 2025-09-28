"""
Дополнительные модели для платежной системы
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from enum import Enum

class PaymentMethod(str, Enum):
    """Методы оплаты"""
    BANK_CARD = "bank_card"
    SBP = "sbp"
    SBER_PAY = "sber_pay"
    YOO_MONEY = "yoo_money"
    QIWI = "qiwi"
    WEBMONEY = "webmoney"

class PaymentProvider(str, Enum):
    """Платежные провайдеры"""
    YOOKASSA = "yookassa"
    CLOUDPAYMENTS = "cloudpayments"

@dataclass
class PaymentRequest:
    """Запрос на создание платежа"""
    user_id: int
    package: str
    amount: Decimal
    method: PaymentMethod
    provider: PaymentProvider
    return_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class PaymentResponse:
    """Ответ на создание платежа"""
    success: bool
    payment_id: Optional[str] = None
    confirmation_url: Optional[str] = None
    amount: Optional[Decimal] = None
    provider: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class PaymentStatus:
    """Статус платежа"""
    payment_id: str
    status: str
    amount: Optional[Decimal] = None
    paid_at: Optional[datetime] = None
    provider_response: Optional[Dict[str, Any]] = None

@dataclass
class WebhookData:
    """Данные webhook уведомления"""
    provider: PaymentProvider
    payment_id: str
    status: str
    amount: Decimal
    metadata: Dict[str, Any]
    signature: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

class PaymentError(Exception):
    """Исключения платежной системы"""
    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(self.message)

class PaymentValidationError(PaymentError):
    """Ошибки валидации платежных данных"""
    pass

class PaymentProviderError(PaymentError):
    """Ошибки платежного провайдера"""
    pass

class PaymentNotFoundError(PaymentError):
    """Платеж не найден"""
    pass

# Константы
PAYMENT_TIMEOUT = 900  # 15 минут на оплату
MAX_PAYMENT_AMOUNT = Decimal('100000.00')  # Максимальная сумма платежа
MIN_PAYMENT_AMOUNT = Decimal('1.00')  # Минимальная сумма платежа

# Маппинг методов оплаты для провайдеров
PAYMENT_METHOD_MAPPING = {
    PaymentProvider.YOOKASSA: {
        PaymentMethod.BANK_CARD: "bank_card",
        PaymentMethod.SBP: "sbp",
        PaymentMethod.SBER_PAY: "sberbank",
        PaymentMethod.YOO_MONEY: "yoo_money",
        PaymentMethod.QIWI: "qiwi",
        PaymentMethod.WEBMONEY: "webmoney"
    },
    PaymentProvider.CLOUDPAYMENTS: {
        PaymentMethod.BANK_CARD: "card",
        PaymentMethod.SBP: "sbp",
        PaymentMethod.SBER_PAY: "sberpay",
        PaymentMethod.YOO_MONEY: "yoomoney"
    }
}

def get_provider_method(provider: PaymentProvider, method: PaymentMethod) -> str:
    """Получение метода оплаты для конкретного провайдера"""
    mapping = PAYMENT_METHOD_MAPPING.get(provider, {})
    return mapping.get(method, method.value)
