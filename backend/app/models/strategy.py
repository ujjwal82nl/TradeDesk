"""Option strategy and strategy leg ORM models."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.order import TransactionType

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount

__all__ = ["StrategyType", "StrategyStatus", "OptionStrategy", "StrategyLeg"]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StrategyType(str, enum.Enum):
    """Recognised multi-leg options strategy types."""

    IRON_FLY = "IRON_FLY"
    IRON_CONDOR = "IRON_CONDOR"
    COVERED_CALL = "COVERED_CALL"
    SHORT_STRANGLE = "SHORT_STRANGLE"
    SHORT_STRADDLE = "SHORT_STRADDLE"
    WHEEL = "WHEEL"


class StrategyStatus(str, enum.Enum):
    """Lifecycle status of an option strategy."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


# ---------------------------------------------------------------------------
# Annotated aliases
# ---------------------------------------------------------------------------
intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class OptionStrategy(Base):
    """A multi-leg option strategy deployed from a :class:`~app.models.broker.BrokerAccount`.

    Greek / payoff metrics (``max_profit``, ``max_loss``, breakevens) are
    calculated at strategy creation and stored for quick retrieval in dashboards.
    """

    __tablename__ = "option_strategies"
    __table_args__ = (
        Index("ix_option_strategies_broker_account_id", "broker_account_id"),
        Index("ix_option_strategies_status", "status"),
        Index("ix_option_strategies_underlying", "underlying"),
        Index("ix_option_strategies_expiry_date", "expiry_date"),
    )

    id: Mapped[intpk]
    broker_account_id: Mapped[int] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_type: Mapped[StrategyType] = mapped_column(
        Enum(StrategyType, name="strategytype"), nullable=False
    )
    underlying: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[StrategyStatus] = mapped_column(
        Enum(StrategyStatus, name="strategystatus"),
        nullable=False,
        default=StrategyStatus.OPEN,
    )
    max_profit: Mapped[money]
    max_loss: Mapped[money]
    breakeven_lower: Mapped[money]
    breakeven_upper: Mapped[money]
    net_premium: Mapped[money]
    margin_used: Mapped[money]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    broker_account: Mapped[BrokerAccount] = relationship(
        "BrokerAccount", back_populates="option_strategies"
    )
    legs: Mapped[list[StrategyLeg]] = relationship(
        "StrategyLeg", back_populates="strategy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<OptionStrategy id={self.id!r} name={self.name!r}"
            f" strategy_type={self.strategy_type!r} status={self.status!r}>"
        )


class StrategyLeg(Base):
    """A single instrument leg within an :class:`OptionStrategy`.

    Each leg references the parent strategy and records the entry conditions,
    live price, and running P&L.
    """

    __tablename__ = "strategy_legs"
    __table_args__ = (
        Index("ix_strategy_legs_strategy_id", "strategy_id"),
        Index("ix_strategy_legs_symbol", "symbol"),
    )

    id: Mapped[intpk]
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("option_strategies.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transactiontype"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Numeric(18, 4), nullable=False)
    strike_price: Mapped[money]
    option_type: Mapped[str | None] = mapped_column(
        String(2), nullable=True, comment="CE or PE"
    )
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_price: Mapped[money]
    current_price: Mapped[money]
    pnl: Mapped[money]

    # Relationships
    strategy: Mapped[OptionStrategy] = relationship(
        "OptionStrategy", back_populates="legs"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<StrategyLeg id={self.id!r} symbol={self.symbol!r}"
            f" option_type={self.option_type!r} pnl={self.pnl!r}>"
        )
