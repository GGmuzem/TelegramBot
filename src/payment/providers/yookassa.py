import json, logging, aiohttp, uuid
from decimal import Decimal
from datetime import datetime
from yookassa import Configuration, Payment  # pip install yookassa
from src.shared.config import settings, PACKAGES
from src.database.crud import PaymentCRUD
from src.database.models import PaymentStatus

logger = logging.getLogger(__name__)
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

class YooKassaProvider:
    def __init__(self):
        self.crud = PaymentCRUD()

    async def create_payment(self, user_id: int, package: str, return_url: str, method="bank_card"):
        if package not in PACKAGES:
            return {"success": False, "error": "unknown package"}
        pack = PACKAGES[package]
        amount = Decimal(str(pack["price"]))
        payment_obj = Payment.create({
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "payment_method_data": {"type": method},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": f"Package {pack['name']} for user {user_id}",
            "metadata": {"user_id": user_id, "package": package}
        }, uuid.uuid4())
        data = json.loads(payment_obj.json())

        await self.crud.create_payment(
            user_id=user_id,
            payment_id=data["id"],
            provider="yookassa",
            amount=amount,
            package_type=package,
            status=PaymentStatus.PENDING,
            metadata=data
        )
        return {
            "success": True,
            "payment_id": data["id"],
            "confirmation_url": data["confirmation"]["confirmation_url"],
            "amount": float(amount)
        }

    async def check_payment_status(self, pid: str):
        payment_obj = Payment.find_one(pid)
        data = json.loads(payment_obj.json())
        return {"status": data["status"]}

    async def cancel_payment(self, pid: str):
        Payment.cancel(pid)
        return {"success": True}

yookassa_provider = YooKassaProvider()
