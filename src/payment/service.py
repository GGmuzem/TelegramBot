"""
Единый сервис для работы с платежами
"""
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from src.payment.providers.yookassa import yookassa_provider
from src.payment.providers.cloudpayments import cloudpayments_provider
from src.database.crud import PaymentCRUD, UserCRUD, TariffCRUD
from src.payment.fiscal import atol_fiscal_service

logger = logging.getLogger(__name__)

class PaymentService:
    """Единый интерфейс для всех платежных провайдеров"""
    
    def __init__(self):
        self.providers = {
            "yookassa": yookassa_provider,
            "cloudpayments": cloudpayments_provider
        }
        self.payment_crud = PaymentCRUD()
        self.user_crud = UserCRUD()
        self.tariff_crud = TariffCRUD()
        self.default_provider = "yookassa"
    
    async def get_tariffs(self):
        """Получение списка активных тарифов"""
        return await self.tariff_crud.get_active_tariffs()

    async def create_payment(
        self,
        user_id: int,
        tariff_id: int,
        method: str = "bank_card",
        provider: Optional[str] = None,
        return_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создание платежа через выбранный провайдер"""
        try:
            # Валидация тарифа
            tariffs = await self.get_tariffs()
            tariff = next((t for t in tariffs if t.id == tariff_id), None)
            if not tariff:
                return {"success": False, "error": "Unknown tariff"}
            
            # Выбор провайдера
            if not provider:
                provider = self.default_provider
            
            if provider not in self.providers:
                return {"success": False, "error": "Unknown payment provider"}
            
            # Проверка пользователя
            user = await self.user_crud.get_by_telegram_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Создание платежа через провайдер
            provider_service = self.providers[provider]
            result = await provider_service.create_payment(
                user_id=user_id,
                amount=tariff.price,
                description=f"Покупка тарифа '{tariff.name}'",
                metadata={'tariff_id': tariff.id},
                method=method,
                return_url=return_url
            )
            
            if result.get("success"):
                logger.info(f"Payment created via {provider}: {result['payment_id']}")
                
                # Дополнительная логика (уведомления, аналитика и т.д.)
                await self._track_payment_created(user_id, tariff.name, result["payment_id"])
            
            return result
            
        except Exception as e:
            logger.error(f"Payment creation failed: {e}")
            return {"success": False, "error": "Internal error"}
    
    async def check_payment_status(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Проверка статуса платежа"""
        try:
            # Получаем информацию о платеже из БД
            payment = await self.payment_crud.get_by_payment_id(payment_id)
            if not payment:
                return None
            
            # Проверяем статус через провайдер
            provider_service = self.providers.get(payment.provider)
            if not provider_service:
                return None
            
            return await provider_service.check_payment_status(payment_id)
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return None
    
    async def cancel_payment(self, payment_id: str) -> Dict[str, Any]:
        """Отмена платежа"""
        try:
            payment = await self.payment_crud.get_by_payment_id(payment_id)
            if not payment:
                return {"success": False, "error": "Payment not found"}
            
            provider_service = self.providers.get(payment.provider)
            if not provider_service:
                return {"success": False, "error": "Provider not found"}
            
            result = await provider_service.cancel_payment(payment_id)
            
            if result.get("success"):
                await self._track_payment_cancelled(payment_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Payment cancellation failed: {e}")
            return {"success": False, "error": "Internal error"}
    
    async def process_successful_payment(self, payment_id: str) -> bool:
        """Обработка успешного платежа"""
        try:
            payment = await self.payment_crud.get_by_payment_id(payment_id)
            if not payment:
                logger.error(f"Payment not found: {payment_id}")
                return False
            
            # Получаем информацию о тарифе
            tariff = await self.tariff_crud.get_by_id(payment.tariff_id)
            if not tariff:
                logger.error(f"Unknown tariff_id: {payment.tariff_id}")
                return False
            
            # Пополняем баланс пользователя
            user = await self.user_crud.get_by_telegram_id(payment.user_id)
            if user:
                new_balance = user.balance + tariff.generations
                await self.user_crud.update_balance(payment.user_id, new_balance)
                
                # Обновляем статистику
                await self.user_crud.update_total_spent(
                    payment.user_id,
                    float(payment.amount)
                )
                
                logger.info(
                    f"Balance updated for user {payment.user_id}: "
                    f"+{tariff.generations} images"
                )

                # Отправка чека
                receipt_items = [{
                    "name": f"Тариф {tariff.name}",
                    "price": float(tariff.price),
                    "quantity": 1,
                    "sum": float(tariff.price),
                    "payment_method": "full_payment",
                    "payment_object": "service",
                    "vat": {"type": "none"} # или другая ставка НДС
                }]
                await atol_fiscal_service.create_receipt(
                    payment_id=payment.payment_id,
                    user_email=f"{user.telegram_id}@telegram.user", # Заглушка, нужно реальное мыло
                    items=receipt_items
                )
                
                # Дополнительные действия
                await self._track_successful_payment(payment_id, payment.user_id, tariff)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to process successful payment: {e}")
            return False
    
    async def get_payment_statistics(self) -> Dict[str, Any]:
        """Статистика по платежам"""
        try:
            stats = {}
            
            for provider_name, provider_service in self.providers.items():
                if hasattr(provider_service, 'get_provider_statistics'):
                    stats[provider_name] = await provider_service.get_provider_statistics()
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get payment statistics: {e}")
            return {}
    
    async def _track_payment_created(self, user_id: int, package: str, payment_id: str):
        """Трекинг создания платежа"""
        # Здесь можно добавить аналитику, уведомления и т.д.
        logger.info(f"Payment tracking: created {payment_id} for user {user_id}")
    
    async def _track_payment_cancelled(self, payment_id: str):
        """Трекинг отмены платежа"""
        logger.info(f"Payment tracking: cancelled {payment_id}")
    
    async def _track_successful_payment(self, payment_id: str, user_id: int, package_info: dict):
        """Трекинг успешного платежа"""
        logger.info(
            f"Payment tracking: success {payment_id}, "
            f"user {user_id}, package {package_info['name']}"
        )

# Глобальный экземпляр
payment_service = PaymentService()
