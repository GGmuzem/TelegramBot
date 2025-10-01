from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, update, func
from src.database.connection import get_session
from src.database.models import User, Payment, PaymentStatus, Tariff

class UserCRUD:
    async def get_or_create_user(self, **kwargs):
        async with get_session() as s:
            user = await s.get(User, kwargs["telegram_id"])
            if not user:
                user = User(**kwargs)
                s.add(user); await s.commit()
            return user

    async def get_by_telegram_id(self, tid: int):
        async with get_session() as s:
            return await s.get(User, tid)

    async def update_balance(self, tid: int, new_balance: int):
        async with get_session() as s:
            await s.execute(update(User).where(User.telegram_id==tid).values(balance=new_balance, last_activity=datetime.now(timezone.utc)))
            await s.commit()

    async def update_total_spent(self, tid: int, add: float):
        async with get_session() as s:
            await s.execute(update(User).where(User.telegram_id==tid).values(total_spent=User.total_spent+Decimal(str(add))))
            await s.commit()

class TariffCRUD:
    async def get_active_tariffs(self):
        async with get_session() as s:
            query = await s.execute(select(Tariff).where(Tariff.is_active == True).order_by(Tariff.price))
            return query.scalars().all()

    async def get_by_id(self, tariff_id: int):
        async with get_session() as s:
            return await s.get(Tariff, tariff_id)

class PaymentCRUD:
    async def create_payment(self, **data):
        async with get_session() as s:
            p = Payment(**data)
            s.add(p); await s.commit(); await s.refresh(p)
            return p

    async def get_by_payment_id(self, pid: str):
        async with get_session() as s:
            q = await s.execute(select(Payment).where(Payment.payment_id==pid))
            return q.scalar_one_or_none()

    async def update_status(self, db_id, status: PaymentStatus, payment_metadata: dict | None = None):
        async with get_session() as s:
            await s.execute(update(Payment).where(Payment.id==db_id).values(status=status, payment_metadata=payment_metadata))
            await s.commit()
    
    async def update_metadata(self, db_id, payment_metadata: dict):
        """Обновление метаданных платежа"""
        async with get_session() as s:
            await s.execute(update(Payment).where(Payment.id==db_id).values(payment_metadata=payment_metadata))
            await s.commit()
