"""
Обработчик webhook уведомлений от платежных систем
"""
import json
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

from src.payment.providers.yookassa import yookassa_provider
from src.payment.providers.cloudpayments import cloudpayments_provider
from src.payment.service import payment_service
from src.shared.security import security_manager

logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Webhook Service")

@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """Webhook для ЮKassa уведомлений"""
    try:
        # Получаем данные
        body = await request.body()
        headers = request.headers
        
        # Проверяем подпись
        signature = headers.get("Authorization", "")
        if not security_manager.verify_webhook_signature(
            body.decode(),
            signature,
            yookassa_provider.webhook_secret or ""
        ):
            logger.warning("Invalid YooKassa webhook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Парсим данные
        webhook_data = json.loads(body.decode())
        
        # Обрабатываем через провайдер
        success = await yookassa_provider.process_webhook(webhook_data)
        
        if success:
            logger.info(f"YooKassa webhook processed: {webhook_data.get('object', {}).get('id')}")
            return PlainTextResponse("OK")
        else:
            logger.error("Failed to process YooKassa webhook")
            raise HTTPException(status_code=400, detail="Processing failed")
        
    except Exception as e:
        logger.error(f"YooKassa webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

@app.post("/webhook/cloudpayments")
async def cloudpayments_webhook(request: Request):
    """Webhook для CloudPayments уведомлений"""
    try:
        # Получаем данные
        body = await request.body()
        headers = request.headers
        
        # Проверяем подпись
        signature = headers.get("Content-HMAC", "")
        webhook_data = json.loads(body.decode())
        
        success = await cloudpayments_provider.process_webhook(webhook_data, signature)
        
        if success:
            logger.info(f"CloudPayments webhook processed: {webhook_data.get('InvoiceId')}")
            return PlainTextResponse("OK")
        else:
            logger.error("Failed to process CloudPayments webhook")
            raise HTTPException(status_code=400, detail="Processing failed")
        
    except Exception as e:
        logger.error(f"CloudPayments webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

@app.get("/health")
async def health_check():
    """Проверка работоспособности webhook сервиса"""
    return {"status": "healthy", "service": "payment-webhook"}

@app.get("/metrics")
async def metrics():
    """Метрики для Prometheus"""
    try:
        stats = await payment_service.get_payment_statistics()
        
        # Простые метрики в формате Prometheus
        metrics_text = []
        
        for provider, provider_stats in stats.items():
            if isinstance(provider_stats, dict):
                for metric, value in provider_stats.items():
                    if isinstance(value, (int, float)):
                        metrics_text.append(
                            f'payment_{metric}{{provider="{provider}"}} {value}'
                        )
        
        return PlainTextResponse("\n".join(metrics_text))
        
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return PlainTextResponse("# Metrics unavailable")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
