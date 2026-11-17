"""Position ORM model — intraday / F&O open positions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount

__all__ = ["Position"]

intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class Position(Base):
    """An open intraday or F&O position for a :class:`~app.models.broker.BrokerAccount`.

    ``option_type`` is ``'CE'`` (Call) or ``'PE'`` (Put); ``None`` for equities.
    ``expiry_date`` and ``strike_price`` are relevant only for derivatives.
    """

    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_broker_account_id", "broker_account_id"),
        Index("ix_positions_symbol", "symbol"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    product_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=0)
    buy_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=0)
    sell_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=0)
    average_price: Mapped[money]
    last_price: Mapped[money]
    pnl: Mapped[money]
    day_pnl: Mapped[money]
    multiplier: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=True)
    instrument_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike_price: Mapped[money]
    option_type: Mapped[str | None] = mapped_column(
        String(2), nullable=True, comment="CE or PE"
    )
    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delta: Mapped[Decimal | None] = mapped_column(Numeric(15, 6), nullable=True)
    gamma: Mapped[Decimal | None] = mapped_column(Numeric(15, 8), nullable=True)
    theta: Mapped[Decimal | None] = mapped_column(Numeric(15, 6), nullable=True)
    vega: Mapped[Decimal | None] = mapped_column(Numeric(15, 6), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    broker_account: Mapped[BrokerAccount] = relationship(
        "BrokerAccount", back_populates="positions"
    )

    @property
    def broker_name(self) -> str:
        if self.broker_account and self.broker_account.broker:
            b_name = self.broker_account.broker.name
            return b_name.value if hasattr(b_name, "value") else str(b_name)
        return ""

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<Position id={self.id!r} symbol={self.symbol!r}"
            f" quantity={self.quantity!r} pnl={self.pnl!r}>"
        )
