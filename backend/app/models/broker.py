"""Broker provider and broker account ORM models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.holding import Holding
    from app.models.position import Position
    from app.models.order import Order
    from app.models.trade import Trade
    from app.models.dividend import Dividend
    from app.models.margin import MarginSnapshot
    from app.models.strategy import OptionStrategy

__all__ = ["BrokerName", "BrokerProvider", "BrokerAccount"]

# ---------------------------------------------------------------------------
# Annotated type aliases
# ---------------------------------------------------------------------------
intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True, index=True)]
now_utc = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]
updated_utc = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class BrokerName(str, enum.Enum):
    """Supported broker integrations."""

    DHAN = "DHAN"
    ZERODHA = "ZERODHA"
    INDMONEY = "INDMONEY"
    IBKR = "IBKR"
    COINDCX = "COINDCX"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class BrokerProvider(Base):
    """Static catalogue of supported broker providers.

    One row per supported broker; seeded at application start-up.
    """

    __tablename__ = "broker_providers"

    id: Mapped[intpk]
    name: Mapped[BrokerName] = mapped_column(
        Enum(BrokerName, name="brokername"), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    accounts: Mapped[list[BrokerAccount]] = relationship(
        "BrokerAccount", back_populates="broker", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<BrokerProvider id={self.id!r} name={self.name!r}"
            f" is_active={self.is_active!r}>"
        )


class BrokerAccount(Base):
    """A user's linked account at a specific broker.

    ``access_token`` and ``refresh_token`` are stored in encrypted form;
    encryption / decryption is handled at the service layer (e.g. using
    ``cryptography.fernet``).
    """

    __tablename__ = "broker_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "broker_id", "account_id", name="uq_user_broker_account"),
        Index("ix_broker_accounts_user_id", "user_id"),
        Index("ix_broker_accounts_broker_id", "broker_id"),
    )

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    broker_id: Mapped[int] = mapped_column(
        ForeignKey("broker_providers.id", ondelete="RESTRICT"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stored encrypted — never store plaintext tokens in the DB.
    access_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[now_utc]
    updated_at: Mapped[updated_utc]

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="broker_accounts")
    broker: Mapped[BrokerProvider] = relationship("BrokerProvider", back_populates="accounts")
    holdings: Mapped[list[Holding]] = relationship(
        "Holding", back_populates="broker_account", cascade="all, delete-orphan"
    )
    positions: Mapped[list[Position]] = relationship(
        "Position", back_populates="broker_account", cascade="all, delete-orphan"
    )
    orders: Mapped[list[Order]] = relationship(
        "Order", back_populates="broker_account", cascade="all, delete-orphan"
    )
    trades: Mapped[list[Trade]] = relationship(
        "Trade", back_populates="broker_account", cascade="all, delete-orphan"
    )
    dividends: Mapped[list[Dividend]] = relationship(
        "Dividend", back_populates="broker_account", cascade="all, delete-orphan"
    )
    margin_snapshots: Mapped[list[MarginSnapshot]] = relationship(
        "MarginSnapshot", back_populates="broker_account", cascade="all, delete-orphan"
    )
    option_strategies: Mapped[list[OptionStrategy]] = relationship(
        "OptionStrategy", back_populates="broker_account", cascade="all, delete-orphan"
    )

    @property
    def is_token_expired(self) -> bool:
        if hasattr(self, "_is_token_expired"):
            return self._is_token_expired
        from datetime import datetime, timezone
        if self.token_expiry:
            exp = self.token_expiry
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return exp < datetime.now(timezone.utc)
        return False

    @is_token_expired.setter
    def is_token_expired(self, val: bool) -> None:
        self._is_token_expired = val

    @property
    def token_status(self) -> str:
        if hasattr(self, "_token_status"):
            return self._token_status
        if not self.is_active:
            return "INACTIVE"
        if self.is_token_expired:
            return "EXPIRED"
        return "ACTIVE"

    @token_status.setter
    def token_status(self, val: str) -> None:
        self._token_status = val

    @property
    def status_message(self) -> str | None:
        if hasattr(self, "_status_message"):
            return self._status_message
        if self.is_token_expired:
            return "Token expired"
        return None

    @status_message.setter
    def status_message(self, val: str | None) -> None:
        self._status_message = val

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<BrokerAccount id={self.id!r} account_id={self.account_id!r}"
            f" user_id={self.user_id!r} is_default={self.is_default!r}>"
        )
