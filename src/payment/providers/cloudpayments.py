"""
CloudPayments провайдер для обработки платежей
Резервный способ оплаты после ЮKassa
"""
import json
import logging
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import aiohttp
from decimal import Decimal

from src.shared.config import settings, PACKAGES
from src.database.crud import PaymentCRUD, UserCRUD
from src.database.models import PaymentStatus

logger = logging.getLogger(__name__)


class CloudPaymentsProvider:
    """Провайдер для работы с CloudPayments API"""
    
    def __init__(self):
        self.api_url = "https://api.cloudpayments.ru"
        self.public_id = settings.CLOUDPAYMENTS_PUBLIC_ID
        self.secret_key = settings.CLOUDPAYMENTS_SECRET_KEY
        self.webhook_secret = getattr(settings, 'CLOUDPAYMENTS_WEBHOOK_SECRET', '')
        
        # CRUD сервисы
        self.payment_crud = PaymentCRUD()
        self.user_crud = UserCRUD()
        
        # Настройки
        self.timeout = 30
        self.max_retries = 3
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Получение заголовков авторизации"""
        auth_string = f"{self.public_id}:{self.secret_key}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        return {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json'
        }
    
    def _calculate_signature(self, data: str) -> str:
        """Вычисление подписи для webhook"""
        if not self.webhook_secret:
            return ""
        
        signature = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode('utf-8'),
                data.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return signature
    
    async def create_payment(
        self,
        user_id: int,
        package: str,
        method: str = "card",
        return_url: str = None
    ) -> Dict[str, Any]:
        """
        Создание платежа в CloudPayments
        
        Args:
            user_id: ID пользователя Telegram
            package: Тип пакета
            method: Способ оплаты
            return_url: URL для возврата
        
        Returns:
            Результат создания платежа
        """
        try:
            if package not in PACKAGES:
                return {
                    'success': False,
                    'error': f'Неизвестный пакет: {package}'
                }
            
            package_info = PACKAGES[package]
            amount = Decimal(str(package_info['price']))
            
            # Создаем запись платежа в БД
            payment_id = f"cp_{user_id}_{int(datetime.now().timestamp())}"
            
            payment_data = {
                'user_id': user_id,
                'payment_id': payment_id,
                'amount': amount,
                'package_type': package,
                'provider': 'cloudpayments',
                'method': method,
                'status': PaymentStatus.PENDING,
                'metadata': {
                    'images_count': package_info['images'],
                    'return_url': return_url,
                    'created_via': 'telegram_bot'
                }
            }
            
            payment = await self.payment_crud.create_payment(**payment_data)
            
            if not payment:
                return {
                    'success': False,
                    'error': 'Не удалось создать запись платежа'
                }
            
            # Получаем данные пользователя
            user = await self.user_crud.get_by_telegram_id(user_id)
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            # Параметры платежа для CloudPayments
            payment_params = {
                "Amount": float(amount),
                "Currency": "RUB",
                "InvoiceId": payment_id,
                "Description": f"Пополнение баланса - {package_info['name']}",
                "AccountId": str(user_id),
                "Email": user.email or f"user{user_id}@telegram.bot",
                "JsonData": json.dumps({
                    "package": package,
                    "images_count": package_info['images'],
                    "telegram_user_id": user_id,
                    "telegram_username": user.username or "",
                    "cloudPayments": True
                }),
                "RequireConfirmation": False,  # Без 3DS если возможно
                "SendEmail": True,
                "InvoiceIdAlt": payment_id
            }
            
            # Добавляем URL для возврата
            if return_url:
                payment_params["SuccessRedirectUrl"] = return_url
                payment_params["FailRedirectUrl"] = f"{return_url}?error=payment_failed"
            
            # Определяем метод оплаты
            api_method = "payments/cards/charge"  # По умолчанию карты
            
            if method == "sbp":
                api_method = "payments/qr/charge"
                payment_params["QrId"] = payment_id
            
            # Отправляем запрос к CloudPayments
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                
                url = f"{self.api_url}/{api_method}"
                headers = self._get_auth_headers()
                
                logger.info(f"Создание платежа CloudPayments: {payment_id}, сумма: {amount}₽")
                
                async with session.post(
                    url,
                    json=payment_params,
                    headers=headers
                ) as response:
                    
                    response_data = await response.json()
                    
                    if response.status == 200 and response_data.get("Success"):
                        # Платеж создан успешно
                        model = response_data.get("Model", {})
                        
                        # Обновляем метаданные платежа
                        await self.payment_crud.update_metadata(
                            payment.id,
                            {
                                **(payment.payment_metadata or {}),
                                'cloudpayments_transaction_id': model.get('TransactionId'),
                                'cloudpayments_response': response_data,
                                'payment_url': model.get('PaReq')  # URL для оплаты
                            }
                        )
                        
                        # Формируем URL для оплаты
                        if method == "card":
                            # Для карт возвращаем URL на форму оплаты
                            payment_url = (
                                f"https://widget.cloudpayments.ru/widgets/cpay?"
                                f"publicid={self.public_id}&"
                                f"invoiceid={payment_id}&"
                                f"amount={amount}&"
                                f"currency=RUB&"
                                f"accountid={user_id}&"
                                f"description={package_info['name']}&"
                                f"email={payment_params['Email']}"
                            )
                        elif method == "sbp":
                            # Для СБП возвращаем QR код
                            payment_url = model.get("QrCodeUrl", "")
                        else:
                            payment_url = model.get("Url", "")
                        
                        result = {
                            'success': True,
                            'payment_id': payment_id,
                            'confirmation_url': payment_url,
                            'amount': float(amount),
                            'transaction_id': model.get('TransactionId'),
                            'provider': 'cloudpayments'
                        }
                        
                        logger.info(f"✅ Платеж CloudPayments создан: {payment_id}")
                        return result
                        
                    else:
                        # Ошибка создания платежа
                        error_message = response_data.get("Message", "Неизвестная ошибка")
                        
                        await self.payment_crud.update_status(
                            payment.id,
                            PaymentStatus.FAILED,
                            {
                                **(payment.payment_metadata or {}),
                                'error': error_message,
                                'cloudpayments_response': response_data
                            }
                        )
                        
                        logger.error(f"❌ Ошибка создания платежа CloudPayments: {error_message}")
                        
                        return {
                            'success': False,
                            'error': f'CloudPayments: {error_message}'
                        }
            
        except aiohttp.ClientTimeout:
            logger.error("Таймаут запроса к CloudPayments")
            return {
                'success': False,
                'error': 'Таймаут соединения с платежной системой'
            }
        except Exception as e:
            logger.error(f"Ошибка создания платежа CloudPayments: {e}")
            return {
                'success': False,
                'error': f'Внутренняя ошибка: {str(e)}'
            }
    
    async def check_payment_status(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Проверка статуса платежа"""
        try:
            # Получаем платеж из базы
            payment = await self.payment_crud.get_by_payment_id(payment_id)
            if not payment:
                return None
            
            transaction_id = payment.payment_metadata.get('cloudpayments_transaction_id')
            if not transaction_id:
                return {'status': 'pending'}
            
            # Запрашиваем статус у CloudPayments
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                
                url = f"{self.api_url}/payments/get"
                headers = self._get_auth_headers()
                params = {"TransactionId": transaction_id}
                
                async with session.post(
                    url,
                    json=params,
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("Success"):
                            model = data.get("Model", {})
                            status = model.get("Status", "").lower()
                            
                            # Маппинг статусов CloudPayments
                            status_mapping = {
                                "completed": "succeeded",
                                "authorized": "succeeded", 
                                "cancelled": "canceled",
                                "declined": "failed",
                                "refunded": "refunded"
                            }
                            
                            return {
                                'status': status_mapping.get(status, status),
                                'transaction_id': transaction_id,
                                'amount': model.get('Amount'),
                                'provider_response': data
                            }
            
            return {'status': 'pending'}
            
        except Exception as e:
            logger.error(f"Ошибка проверки статуса CloudPayments: {e}")
            return None
    
    async def cancel_payment(self, payment_id: str) -> Dict[str, Any]:
        """Отмена платежа"""
        try:
            # Получаем платеж из базы
            payment = await self.payment_crud.get_by_payment_id(payment_id)
            if not payment:
                return {
                    'success': False,
                    'error': 'Платеж не найден'
                }
            
            transaction_id = payment.payment_metadata.get('cloudpayments_transaction_id')
            if not transaction_id:
                # Платеж еще не был отправлен в CloudPayments
                await self.payment_crud.update_status(
                    payment.id,
                    PaymentStatus.CANCELED
                )
                
                return {
                    'success': True,
                    'message': 'Платеж отменен локально'
                }
            
            # Отменяем платеж в CloudPayments
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                
                url = f"{self.api_url}/payments/void"
                headers = self._get_auth_headers()
                params = {"TransactionId": transaction_id}
                
                async with session.post(
                    url,
                    json=params,
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("Success"):
                            # Обновляем статус в базе
                            await self.payment_crud.update_status(
                                payment.id,
                                PaymentStatus.CANCELED,
                                {
                                    **(payment.payment_metadata or {}),
                                    'canceled_at': datetime.now().isoformat(),
                                    'cancel_response': data
                                }
                            )
                            
                            return {
                                'success': True,
                                'message': 'Платеж успешно отменен'
                            }
                        else:
                            return {
                                'success': False,
                                'error': data.get('Message', 'Не удалось отменить платеж')
                            }
                    else:
                        return {
                            'success': False,
                            'error': f'HTTP {response.status}'
                        }
            
        except Exception as e:
            logger.error(f"Ошибка отмены платежа CloudPayments: {e}")
            return {
                'success': False,
                'error': f'Внутренняя ошибка: {str(e)}'
            }
    
    async def process_webhook(self, webhook_data: Dict[str, Any], signature: str) -> bool:
        """
        Обработка webhook уведомлений от CloudPayments
        
        Args:
            webhook_data: Данные webhook
            signature: Подпись запроса
        
        Returns:
            True если успешно обработано
        """
        try:
            # Проверяем подпись
            if self.webhook_secret:
                expected_signature = self._calculate_signature(json.dumps(webhook_data))
                if not hmac.compare_digest(signature, expected_signature):
                    logger.warning("Неверная подпись webhook CloudPayments")
                    return False
            
            # Извлекаем данные
            invoice_id = webhook_data.get("InvoiceId")
            transaction_id = webhook_data.get("TransactionId")
            status = webhook_data.get("Status", "").lower()
            amount = webhook_data.get("Amount", 0)
            
            logger.info(f"Webhook CloudPayments: {invoice_id}, статус: {status}")
            
            if not invoice_id:
                logger.error("Отсутствует InvoiceId в webhook CloudPayments")
                return False
            
            # Получаем платеж из базы
            payment = await self.payment_crud.get_by_payment_id(invoice_id)
            if not payment:
                logger.warning(f"Платеж не найден в базе: {invoice_id}")
                return False
            
            # Обрабатываем в зависимости от статуса
            if status == "completed":
                return await self._handle_payment_success(payment, webhook_data)
            elif status in ["cancelled", "declined"]:
                return await self._handle_payment_failed(payment, webhook_data)
            else:
                logger.info(f"Неизвестный статус CloudPayments: {status}")
                return True
            
        except Exception as e:
            logger.error(f"Ошибка обработки webhook CloudPayments: {e}")
            return False
    
    async def _handle_payment_success(self, payment, webhook_data: Dict[str, Any]) -> bool:
        """Обработка успешного платежа"""
        try:
            # Обновляем статус платежа
            await self.payment_crud.update_status(
                payment.id,
                PaymentStatus.SUCCEEDED,
                {
                    **(payment.payment_metadata or {}),
                    'cloudpayments_webhook': webhook_data,
                    'completed_at': datetime.now().isoformat()
                }
            )
            
            # Пополняем баланс пользователя
            user = await self.user_crud.get_by_telegram_id(payment.user_id)
            if user:
                images_count = (payment.payment_metadata or {}).get('images_count', 1)
                new_balance = user.balance + images_count
                
                await self.user_crud.update_balance(payment.user_id, new_balance)
                
                # Обновляем статистику пользователя
                await self.user_crud.update_total_spent(
                    payment.user_id,
                    float(payment.amount)
                )
                
                logger.info(
                    f"✅ CloudPayments: Пользователь {payment.user_id} пополнил баланс на {images_count} изображений"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обработки успешного платежа CloudPayments: {e}")
            return False
    
    async def _handle_payment_failed(self, payment, webhook_data: Dict[str, Any]) -> bool:
        """Обработка неуспешного платежа"""
        try:
            status = PaymentStatus.CANCELED if webhook_data.get("Status") == "Cancelled" else PaymentStatus.FAILED
            
            await self.payment_crud.update_status(
                payment.id,
                status,
                {
                    **(payment.payment_metadata or {}),
                    'cloudpayments_webhook': webhook_data,
                    'failed_at': datetime.now().isoformat(),
                    'failure_reason': webhook_data.get('Reason', 'Unknown')
                }
            )
            
            logger.info(f"CloudPayments: Платеж {payment.payment_id} завершился неуспешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обработки неуспешного платежа CloudPayments: {e}")
            return False
    
    def get_provider_name(self) -> str:
        """Название провайдера"""
        return "CloudPayments"
    
    def is_configured(self) -> bool:
        """Проверка настройки провайдера"""
        return bool(self.public_id and self.secret_key)
    
    async def get_provider_statistics(self) -> Dict[str, Any]:
        """Статистика провайдера"""
        try:
            # Получаем статистику платежей CloudPayments из базы
            stats = await self.payment_crud.get_provider_statistics('cloudpayments')
            
            return {
                'provider': 'CloudPayments',
                'configured': self.is_configured(),
                'total_payments': stats.get('total_payments', 0),
                'successful_payments': stats.get('successful_payments', 0),
                'total_amount': float(stats.get('total_amount', 0)),
                'success_rate': stats.get('success_rate', 0.0),
                'average_amount': float(stats.get('average_amount', 0))
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики CloudPayments: {e}")
            return {
                'provider': 'CloudPayments',
                'configured': self.is_configured(),
                'error': str(e)
            }


# Глобальный экземпляр провайдера
cloudpayments_provider = CloudPaymentsProvider()