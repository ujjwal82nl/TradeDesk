"""Dividend ORM model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount

__all__ = ["Dividend"]

intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class Dividend(Base):
    """Dividend receipt record for a :class:`~app.models.broker.BrokerAccount`.

    Both ``ex_date`` (eligibility cut-off) and ``payment_date`` (credit date)
    are stored to support accurate income analytics.
    """

    __tablename__ = "dividends"
    __table_args__ = (
        Index("ix_dividends_broker_account_id", "broker_account_id"),
        Index("ix_dividends_symbol", "symbol"),
        Index("ix_dividends_isin", "isin"),
        Index("ix_dividends_ex_date", "ex_date"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ex_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dividend_per_share: Mapped[money]
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_dividend: Mapped[money]
    tax_deducted: Mapped[money]
    net_dividend: Mapped[money]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    broker_account: Mapped[BrokerAccount] = relationship(
        "BrokerAccount", back_populates="dividends"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<Dividend id={self.id!r} symbol={self.symbol!r}"
            f" net_dividend={self.net_dividend!r} ex_date={self.ex_date!r}>"
        )
