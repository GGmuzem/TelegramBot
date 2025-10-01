import logging
import aiohttp
from datetime import datetime, timezone
from src.shared.config import settings

logger = logging.getLogger(__name__)

class AtolFiscalService:
    API_URL = "https://online.atol.ru/possystem/v4"

    async def _get_token(self):
        url = f"{self.API_URL}/getToken"
        payload = {"login": settings.ATOL_LOGIN, "pass": settings.ATOL_PASSWORD}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("token")
                else:
                    logger.error(f"Atol getToken failed: {await resp.text()}")
                    return None

    async def create_receipt(self, payment_id: str, user_email: str, items: list):
        if not all([settings.ATOL_LOGIN, settings.ATOL_PASSWORD, settings.ATOL_GROUP_CODE]):
            logger.warning("Atol fiscalization is not configured.")
            return {"success": False, "error": "Not configured"}

        token = await self._get_token()
        if not token:
            return {"success": False, "error": "Auth failed"}
        
        url = f"{self.API_URL}/{settings.ATOL_GROUP_CODE}/sell?token={token}"
        
        receipt = {
            "external_id": payment_id,
            "timestamp": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S"),
            "receipt": {
                "client": {"email": user_email},
                "company": {
                    "inn": settings.ATOL_COMPANY_INN,
                    "payment_address": settings.ATOL_PAYMENT_ADDRESS
                },
                "items": items,
                "payments": [{
                    "type": 1, # 1 - электронными
                    "sum": sum(item['sum'] for item in items)
                }],
                "total": sum(item['sum'] for item in items)
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=receipt) as resp:
                response_data = await resp.json()
                if resp.status == 200 and response_data.get("status") == "wait":
                    logger.info(f"Atol receipt created for payment {payment_id}")
                    return {"success": True, "uuid": response_data.get("uuid")}
                else:
                    logger.error(f"Atol create_receipt failed: {response_data}")
                    return {"success": False, "error": response_data.get("error", {}).get("text")}

atol_fiscal_service = AtolFiscalService()
