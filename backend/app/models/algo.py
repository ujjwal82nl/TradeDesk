"""AlgoRun and TradeSignal ORM models."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.order import TransactionType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.order import Order
    from app.models.broker import BrokerAccount

__all__ = ["AlgoStatus", "AlgoMode", "SignalType", "AlgoRun", "TradeSignal", "AlgoStrategy"]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AlgoStatus(str, enum.Enum):
    """Runtime state of an algorithmic trading run."""

    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class AlgoMode(str, enum.Enum):
    """Execution mode of an algo run."""

    PAPER = "PAPER"
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"


class SignalType(str, enum.Enum):
    """Direction / intent of a trade signal."""

    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"


# ---------------------------------------------------------------------------
# Annotated aliases
# ---------------------------------------------------------------------------
intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class AlgoRun(Base):
    """An execution session for an algorithmic trading strategy.

    ``strategy_code`` holds the Python source or a reference to the strategy
    module name, stored so the exact version used in any run can be audited.
    ``config`` is a free-form JSON blob (e.g. lot size, risk limits).
    ``logs`` captures streaming stdout/stderr from the algo process.
    """

    __tablename__ = "algo_runs"
    __table_args__ = (
        Index("ix_algo_runs_user_id", "user_id"),
        Index("ix_algo_runs_status", "status"),
        Index("ix_algo_runs_mode", "mode"),
    )

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AlgoStatus] = mapped_column(
        Enum(AlgoStatus, name="algostatus"),
        nullable=False,
        default=AlgoStatus.STOPPED,
    )
    mode: Mapped[AlgoMode] = mapped_column(
        Enum(AlgoMode, name="algomode"),
        nullable=False,
        default=AlgoMode.PAPER,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="algo_runs")
    signals: Mapped[list[TradeSignal]] = relationship(
        "TradeSignal", back_populates="algo_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<AlgoRun id={self.id!r} name={self.name!r}"
            f" status={self.status!r} mode={self.mode!r}>"
        )


class TradeSignal(Base):
    """A single trade signal emitted by an :class:`AlgoRun`.

    When the signal is acted upon, ``executed`` is set to ``True`` and
    ``executed_at`` / ``order_id`` are populated by the execution service.
    ``confidence_score`` is a float in [0, 1] produced by the strategy.
    """

    __tablename__ = "trade_signals"
    __table_args__ = (
        Index("ix_trade_signals_algo_run_id", "algo_run_id"),
        Index("ix_trade_signals_symbol", "symbol"),
        Index("ix_trade_signals_executed", "executed"),
        Index("ix_trade_signals_created_at", "created_at"),
    )

    id: Mapped[intpk]
    algo_run_id: Mapped[int] = mapped_column(
        ForeignKey("algo_runs.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_type: Mapped[SignalType] = mapped_column(
        Enum(SignalType, name="signaltype"), nullable=False
    )
    price: Mapped[money]
    quantity: Mapped[int] = mapped_column(Numeric(18, 4), nullable=False)
    strategy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True, comment="Float in [0, 1]"
    )
    executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Nullable FK — set only when the signal has been routed to the broker.
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    algo_run: Mapped[AlgoRun] = relationship("AlgoRun", back_populates="signals")
    order: Mapped[Order | None] = relationship("Order")

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<TradeSignal id={self.id!r} symbol={self.symbol!r}"
            f" signal_type={self.signal_type!r} executed={self.executed!r}>"
        )


class AlgoStrategy(Base):
    """Configured algorithmic strategy definition with entry, exit, and leg parameters."""

    __tablename__ = "algo_strategies"
    __table_args__ = (
        Index("ix_algo_strategies_user_id", "user_id"),
        Index("ix_algo_strategies_is_active", "is_active"),
        Index("ix_algo_strategies_underlying", "underlying"),
    )

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    broker_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    template_type: Mapped[str] = mapped_column(String(100), nullable=False, default="CUSTOM")
    underlying: Mapped[str] = mapped_column(String(50), nullable=False, default="NIFTY")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="LIVE", nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), default="MIS", nullable=False)
    entry_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exit_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    legs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="algo_strategies")
    broker_account: Mapped[BrokerAccount | None] = relationship("BrokerAccount")

    def __repr__(self) -> str:
        return f"<AlgoStrategy id={self.id!r} name={self.name!r} active={self.is_active!r}>"
