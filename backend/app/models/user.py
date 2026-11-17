"""User ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.broker import BrokerAccount
    from app.models.portfolio_snapshot import PortfolioSnapshot
    from app.models.algo import AlgoRun, AlgoStrategy

__all__ = ["User"]

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


class User(Base):
    """Application user account.

    Each user may own multiple :class:`~app.models.broker.BrokerAccount`
    instances and multiple :class:`~app.models.algo.AlgoRun` instances.
    """

    __tablename__ = "users"

    id: Mapped[intpk]
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[now_utc]
    updated_at: Mapped[updated_utc]

    # Relationships
    broker_accounts: Mapped[list[BrokerAccount]] = relationship(
        "BrokerAccount", back_populates="user", cascade="all, delete-orphan"
    )
    portfolio_snapshots: Mapped[list[PortfolioSnapshot]] = relationship(
        "PortfolioSnapshot", back_populates="user", cascade="all, delete-orphan"
    )
    algo_runs: Mapped[list[AlgoRun]] = relationship(
        "AlgoRun", back_populates="user", cascade="all, delete-orphan"
    )
    algo_strategies: Mapped[list[AlgoStrategy]] = relationship(
        "AlgoStrategy", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<User id={self.id!r} email={self.email!r} is_active={self.is_active!r}>"
        )
