"""Holding ORM model — long-term equity/MF positions held in demat."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, List

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount

__all__ = ["Holding", "HoldingLot", "BrokerTradeHistory"]

intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class Holding(Base):
    """A single demat holding entry for a :class:`~app.models.broker.BrokerAccount`.

    Quantities and prices are refreshed on every sync from the broker API.
    Monetary values use ``Numeric(18, 4)`` to avoid floating-point drift.
    """

    __tablename__ = "holdings"
    __table_args__ = (
        Index("ix_holdings_broker_account_id", "broker_account_id"),
        Index("ix_holdings_symbol", "symbol"),
        Index("ix_holdings_isin", "isin"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    average_cost: Mapped[money]
    current_price: Mapped[money]
    current_value: Mapped[money]
    pnl: Mapped[money]
    pnl_percent: Mapped[money]
    day_change: Mapped[money]
    day_change_percent: Mapped[money]
    product_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    instrument_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    broker_account: Mapped[BrokerAccount] = relationship(
        "BrokerAccount", back_populates="holdings"
    )
    lots: Mapped[List[HoldingLot]] = relationship(
        "HoldingLot", back_populates="holding", cascade="all, delete-orphan"
    )

    @property
    def broker_name(self) -> str:
        if self.broker_account and self.broker_account.broker:
            b_name = self.broker_account.broker.name
            return b_name.value if hasattr(b_name, "value") else str(b_name)
        return ""

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<Holding id={self.id!r} symbol={self.symbol!r}"
            f" quantity={self.quantity!r} pnl={self.pnl!r}>"
        )


class BrokerTradeHistory(Base):
    """Archival record of historical executed trades pulled from broker APIs.

    Ensures trades are persisted permanently in the local database, eliminating
    API latency and rate limits on subsequent holding lot evaluations.
    """

    __tablename__ = "broker_trade_history"
    __table_args__ = (
        Index("ix_bth_account_id", "broker_account_id"),
        Index("ix_bth_symbol", "symbol"),
        Index("ix_bth_isin", "isin"),
        Index("ix_bth_exchange_time", "exchange_time"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    trade_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_symbol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exchange_segment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY or SELL
    product_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    traded_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    traded_price: Mapped[money]
    trade_value: Mapped[money]
    exchange_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    broker_account: Mapped[BrokerAccount] = relationship("BrokerAccount")


class HoldingLot(Base):
    """A computed open buy trade execution (tax lot) linked to a Holding.

    Persisted in the local database to eliminate latency on every page view.
    """

    __tablename__ = "holding_lots"
    __table_args__ = (
        Index("ix_holding_lots_holding_id", "holding_id"),
        Index("ix_holding_lots_broker_account_id", "broker_account_id"),
        Index("ix_holding_lots_order_id", "order_id"),
    )

    id: Mapped[intpk]
    holding_id: Mapped[int] = mapped_column(
        ForeignKey("holdings.id", ondelete="CASCADE"), nullable=False
    )
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    trade_id: Mapped[str] = mapped_column(String(100), nullable=False)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), default="BUY", nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[money]
    amount: Mapped[money]
    exchange: Mapped[str] = mapped_column(String(20), default="NSE", nullable=False)
    is_opening_lot: Mapped[bool] = mapped_column(nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    holding: Mapped[Holding] = relationship("Holding", back_populates="lots")
    broker_account: Mapped[BrokerAccount] = relationship("BrokerAccount")
