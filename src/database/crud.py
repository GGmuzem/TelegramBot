from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.connection import get_session
from src.database.models import User, Payment, PaymentStatus, Tariff, Generation

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
    
    async def update_last_activity(self, tid: int):
        async with get_session() as s:
            await s.execute(update(User).where(User.telegram_id==tid).values(last_activity=datetime.now(timezone.utc)))
            await s.commit()

class TariffCRUD:
    async def get_active_tariffs(self):
        async with get_session() as s:
            query = await s.execute(select(Tariff).where(Tariff.is_active == True).order_by(Tariff.price))
            return query.scalars().all()

    async def get_by_id(self, tariff_id: int):
        async with get_session() as s:
            return await s.get(Tariff, tariff_id)

class GenerationCRUD:
    """CRUD операции для генераций изображений"""
    
    @staticmethod
    async def create_generation(
        session: AsyncSession,
        user_id: int,
        prompt: str,
        style: str,
        quality: str,
        size: str = "512x512",
        status: str = "pending"
    ) -> Generation:
        """Создание новой генерации"""
        generation = Generation(
            user_id=user_id,
            prompt=prompt,
            style=style,
            quality=quality,
            size=size,
            status=status,
            created_at=datetime.now(timezone.utc)
        )
        session.add(generation)
        await session.commit()
        await session.refresh(generation)
        return generation
    
    @staticmethod
    async def get_generation(session: AsyncSession, generation_id: int) -> Optional[Generation]:
        """Получение генерации по ID"""
        result = await session.execute(
            select(Generation).where(Generation.id == generation_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_generations(
        session: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[Generation]:
        """Получение истории генераций пользователя"""
        result = await session.execute(
            select(Generation)
            .where(Generation.user_id == user_id)
            .order_by(Generation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update_generation_status(
        session: AsyncSession,
        generation_id: int,
        status: str,
        image_url: str = None
    ) -> None:
        """Обновление статуса генерации"""
        values = {"status": status}
        if image_url:
            values["image_url"] = image_url
        if status == "completed":
            values["completed_at"] = datetime.now(timezone.utc)
        
        await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(**values)
        )
        await session.commit()
    
    @staticmethod
    async def get_pending_generations(session: AsyncSession) -> List[Generation]:
        """Получение всех ожидающих генераций"""
        result = await session.execute(
            select(Generation)
            .where(Generation.status == "pending")
            .order_by(Generation.created_at.asc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def delete_generation(session: AsyncSession, generation_id: int) -> None:
        """Удаление генерации"""
        await session.execute(
            delete(Generation).where(Generation.id == generation_id)
        )
        await session.commit()

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
