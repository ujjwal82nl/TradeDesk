"""Order ORM model."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount
    from app.models.trade import Trade

__all__ = ["TransactionType", "OrderType", "OrderStatus", "Order"]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TransactionType(str, enum.Enum):
    """Direction of an order."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    """Execution algorithm for an order."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class OrderStatus(str, enum.Enum):
    """Lifecycle state of an order."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ---------------------------------------------------------------------------
# Annotated aliases
# ---------------------------------------------------------------------------
intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class Order(Base):
    """A broker order placed from a :class:`~app.models.broker.BrokerAccount`.

    ``broker_order_id`` is the exchange/broker-assigned identifier and must
    be stored for reconciliation; it may arrive after initial placement.
    """

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_broker_account_id", "broker_account_id"),
        Index("ix_orders_broker_order_id", "broker_order_id"),
        Index("ix_orders_symbol", "symbol"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_order_timestamp", "order_timestamp"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transactiontype"), nullable=False
    )
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType, name="ordertype"), nullable=False
    )
    product_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[money]
    trigger_price: Mapped[money]
    average_price: Mapped[money]
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="orderstatus"),
        nullable=False,
        default=OrderStatus.PENDING,
        index=True,
    )
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exchange_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    broker_account: Mapped[BrokerAccount] = relationship(
        "BrokerAccount", back_populates="orders"
    )
    trades: Mapped[list[Trade]] = relationship(
        "Trade", back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<Order id={self.id!r} symbol={self.symbol!r}"
            f" transaction_type={self.transaction_type!r} status={self.status!r}>"
        )
