"""Margin snapshot ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount

__all__ = ["MarginSnapshot"]

intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class MarginSnapshot(Base):
    """Point-in-time margin utilisation snapshot for a broker account.

    Snapshots are written every time the broker margin API is polled so that
    historical margin usage can be charted over the trading day.
    """

    __tablename__ = "margin_snapshots"
    __table_args__ = (
        Index("ix_margin_snapshots_broker_account_id", "broker_account_id"),
        Index("ix_margin_snapshots_timestamp", "timestamp"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    available_margin: Mapped[money]
    used_margin: Mapped[money]
    span_margin: Mapped[money]
    exposure_margin: Mapped[money]
    collateral: Mapped[money]
    cash_balance: Mapped[money]
    total_balance: Mapped[money]
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    broker_account: Mapped[BrokerAccount] = relationship(
        "BrokerAccount", back_populates="margin_snapshots"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<MarginSnapshot id={self.id!r}"
            f" available_margin={self.available_margin!r}"
            f" timestamp={self.timestamp!r}>"
        )
