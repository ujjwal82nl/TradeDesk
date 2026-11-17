"""Trade ORM model — individual fills associated with orders."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.order import TransactionType

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount
    from app.models.order import Order

__all__ = ["Trade"]

intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class Trade(Base):
    """A single fill (trade execution) linked to an :class:`~app.models.order.Order`.

    One order can produce multiple fills; each is recorded as a separate
    ``Trade`` row.  ``journal_entry`` is a free-form rich-text field the user
    can use for post-trade review notes.
    """

    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_broker_account_id", "broker_account_id"),
        Index("ix_trades_order_id", "order_id"),
        Index("ix_trades_symbol", "symbol"),
        Index("ix_trades_trade_timestamp", "trade_timestamp"),
        Index("ix_trades_broker_trade_id", "broker_trade_id"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    broker_trade_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transactiontype"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[money]
    trade_value: Mapped[money]
    product_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trade_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    journal_entry: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    broker_account: Mapped[BrokerAccount] = relationship(
        "BrokerAccount", back_populates="trades"
    )
    order: Mapped[Order] = relationship("Order", back_populates="trades")

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<Trade id={self.id!r} symbol={self.symbol!r}"
            f" transaction_type={self.transaction_type!r} price={self.price!r}>"
        )
