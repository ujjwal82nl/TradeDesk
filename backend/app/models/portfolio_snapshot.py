"""Portfolio snapshot ORM model — daily net-worth roll-up per user."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User

__all__ = ["PortfolioSnapshot"]

intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class PortfolioSnapshot(Base):
    """Aggregated end-of-day (or intraday) portfolio roll-up for a :class:`~app.models.user.User`.

    Rows are keyed by ``(user_id, snapshot_date)``; the application layer
    upserts on this composite key so that each user has at most one snapshot
    per calendar date (the latest intraday value wins on trading days).
    """

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        Index("ix_portfolio_snapshots_user_id", "user_id"),
        Index("ix_portfolio_snapshots_snapshot_date", "snapshot_date"),
        Index(
            "ix_portfolio_snapshots_user_date",
            "user_id",
            "snapshot_date",
            unique=True,
        ),
    )

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    total_net_worth: Mapped[money]
    total_portfolio_value: Mapped[money]
    today_pnl: Mapped[money]
    unrealized_pnl: Mapped[money]
    realized_pnl: Mapped[money]
    total_cash: Mapped[money]
    total_margin_used: Mapped[money]
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="portfolio_snapshots")

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<PortfolioSnapshot id={self.id!r} user_id={self.user_id!r}"
            f" snapshot_date={self.snapshot_date!r}"
            f" total_net_worth={self.total_net_worth!r}>"
        )
