import enum, uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Enum, DateTime, Boolean, String, Integer, BigInteger, Numeric, ForeignKey, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship, DeclarativeBase
from typing import Optional

class Base(DeclarativeBase): pass

class PaymentStatus(str, enum.Enum):
    PENDING="pending"; SUCCEEDED="succeeded"; CANCELED="canceled"; FAILED="failed"; REFUNDED="refunded"

class GenerationStatus(str, enum.Enum):
    PENDING="pending"; PROCESSING="processing"; COMPLETED="completed"; FAILED="failed"

class User(Base):
    __tablename__ = "users"
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username:    Mapped[str | None]
    first_name:  Mapped[str]
    last_name:   Mapped[str | None]
    balance:     Mapped[int] = mapped_column(Integer, default=0)
    is_admin:    Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # — Подписка
    subscription_type: Mapped[str | None] = mapped_column(String, default=None)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    # — статистика
    total_generations: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)

    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    
    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
    
    @property
    def status(self) -> str:
        """Статус пользователя (active/banned/etc)"""
        return "active"  # По умолчанию active

class Tariff(Base):
    __tablename__ = "tariffs"
    id:          Mapped[int] = mapped_column(primary_key=True)
    name:        Mapped[str]
    price:       Mapped[Decimal] = mapped_column(Numeric(10,2))
    generations: Mapped[int]
    image_size:  Mapped[str]
    priority:    Mapped[bool] = mapped_column(Boolean, default=False)
    is_active:   Mapped[bool] = mapped_column(Boolean, default=True)

class Payment(Base):
    __tablename__ = "payments"
    id:          Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id:  Mapped[str]       = mapped_column(String, unique=True, index=True)
    user_id:     Mapped[int]       = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    tariff_id:   Mapped[int | None] = mapped_column(ForeignKey("tariffs.id"))
    provider:    Mapped[str]
    amount:      Mapped[Decimal]   = mapped_column(Numeric(10,2))
    status:      Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    created_at:  Mapped[datetime]  = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    payment_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)

    user: Mapped[User] = relationship(back_populates="payments")

class Generation(Base):
    __tablename__ = "generations"
    id:           Mapped[int] = mapped_column(primary_key=True)
    user_id:      Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    prompt:       Mapped[str] = mapped_column(String(1000))
    style:        Mapped[str]
    quality:      Mapped[str]
    size:         Mapped[str] = mapped_column(default="512x512")
    status:       Mapped[GenerationStatus] = mapped_column(Enum(GenerationStatus), default=GenerationStatus.PENDING)
    image_url:    Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
