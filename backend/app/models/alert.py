"""
ORM models for Real-Time Indicator Alerts and Telegram Notifications.
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import (
    Boolean,
    DateTime,
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

if TYPE_CHECKING:
    from app.models.user import User

__all__ = ["AlertRule", "AlertNotification", "SignalState"]

intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
money = Annotated[Decimal, mapped_column(Numeric(18, 4), nullable=True)]


class SignalState(str, enum.Enum):
    GREEN = "GREEN"  # Bullish / Buy
    RED = "RED"      # Bearish / Sell
    NEUTRAL = "NEUTRAL"


class AlertRule(Base):
    """Configuration for an automated indicator alert rule (e.g. SuperTrend 16, 1.5 on 90m)."""

    __tablename__ = "alert_rules"
    __table_args__ = (
        Index("ix_alert_rules_user_id", "user_id"),
        Index("ix_alert_rules_symbol", "symbol"),
        Index("ix_alert_rules_is_active", "is_active"),
    )

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. BTCUSD
    exchange: Mapped[str] = mapped_column(String(32), default="BINANCE", nullable=False)
    timeframe: Mapped[str] = mapped_column(String(32), default="90m", nullable=False)  # e.g. 90m, 1h, 15m
    indicator: Mapped[str] = mapped_column(String(64), default="SUPERTREND", nullable=False)
    params: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {"period": 16, "multiplier": 1.5},
    )

    # Runtime indicator state
    current_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)  # GREEN or RED
    current_value: Mapped[money] = mapped_column(Numeric(18, 4), nullable=True)
    current_spot: Mapped[money] = mapped_column(Numeric(18, 4), nullable=True)

    last_flip_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_telegram: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    notifications: Mapped[list[AlertNotification]] = relationship(
        "AlertNotification", back_populates="rule", cascade="all, delete-orphan"
    )


class AlertNotification(Base):
    """Log of dispatched or attempted notifications (e.g. Telegram message)."""

    __tablename__ = "alert_notifications"
    __table_args__ = (
        Index("ix_alert_notifications_rule_id", "rule_id"),
        Index("ix_alert_notifications_created_at", "created_at"),
    )

    id: Mapped[intpk]
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), default="SIGNAL_FLIP", nullable=False)
    old_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_signal: Mapped[str] = mapped_column(String(32), nullable=False)
    spot_price: Mapped[money] = mapped_column(Numeric(18, 4), nullable=True)
    indicator_value: Mapped[money] = mapped_column(Numeric(18, 4), nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="TELEGRAM", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="SENT", nullable=False)  # SENT, FAILED
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rule: Mapped[AlertRule] = relationship("AlertRule", back_populates="notifications")

