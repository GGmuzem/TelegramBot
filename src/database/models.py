import enum, uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Enum, DateTime, Boolean, String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship, DeclarativeBase

class Base(DeclarativeBase): pass

class PaymentStatus(str, enum.Enum):
    PENDING="pending"; SUCCEEDED="succeeded"; CANCELED="canceled"; FAILED="failed"; REFUNDED="refunded"

class User(Base):
    __tablename__ = "users"
    telegram_id: Mapped[int] = mapped_column(primary_key=True)
    username:    Mapped[str | None]
    first_name:  Mapped[str]
    last_name:   Mapped[str | None]
    balance:     Mapped[int] = mapped_column(Integer, default=0)
    is_admin:    Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # — статистика
    total_generations: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)

    payments: Mapped[list["Payment"]] = relationship(back_populates="user")

class Payment(Base):
    __tablename__ = "payments"
    id:          Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id:  Mapped[str]       = mapped_column(String, unique=True, index=True)
    user_id:     Mapped[int]       = mapped_column(ForeignKey("users.telegram_id"))
    provider:    Mapped[str]
    amount:      Mapped[Decimal]   = mapped_column(Numeric(10,2))
    package_type:Mapped[str]
    status:      Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    created_at:  Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)
    metadata:    Mapped[dict]      = mapped_column(default=dict)

    user: Mapped[User] = relationship(back_populates="payments")
