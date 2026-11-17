"""
Positions endpoints.

Exposes open intraday/overnight positions across brokers, with dedicated
views for option positions (with Greeks) and portfolio-level net Greeks.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.position import (
    GreeksSummary,
    OptionPositionResponse,
    PositionResponse,
)
from app.services.positions_service import PositionsService

router = APIRouter()


class SyncPositionsResponse(BaseModel):
    """Result of a positions sync."""

    synced_at: str
    total_positions_synced: int = 0
    broker_results: dict = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[PositionResponse],
    summary="All open positions across brokers",
)
async def list_positions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    broker_account_id: Optional[int] = Query(None, description="Filter by broker account ID"),
) -> List[PositionResponse]:
    """Return all non-zero net positions."""
    service = PositionsService(db, current_user.id)
    return await service.get_all_positions(broker_account_id=broker_account_id)


@router.get(
    "/options",
    response_model=List[OptionPositionResponse],
    summary="Option positions with live Greeks",
)
async def option_positions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    underlying: Optional[str] = Query(None, description="Filter by underlying, e.g. NIFTY"),
    broker_account_id: Optional[int] = Query(None, description="Filter by broker account ID"),
) -> List[OptionPositionResponse]:
    """Return option positions enriched with Greeks."""
    service = PositionsService(db, current_user.id)
    return await service.get_option_positions(
        underlying=underlying,
        broker_account_id=broker_account_id,
    )


@router.get(
    "/greeks",
    response_model=GreeksSummary,
    summary="Portfolio-level net Greeks",
)
async def greeks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    underlying: Optional[str] = Query(None, description="Filter by underlying"),
) -> GreeksSummary:
    """Aggregate Greeks across open option positions."""
    service = PositionsService(db, current_user.id)
    return await service.calculate_greeks_summary(underlying=underlying)


@router.get(
    "/greeks-summary",
    response_model=GreeksSummary,
    summary="Portfolio-level net Greeks (alias)",
)
async def greeks_summary_alias(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    underlying: Optional[str] = Query(None),
) -> GreeksSummary:
    """Alias for /greeks."""
    return await greeks(current_user, db, underlying)


@router.post(
    "/sync",
    response_model=SyncPositionsResponse,
    summary="Sync positions from all brokers",
)
async def sync_positions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyncPositionsResponse:
    """Pull and persist the latest positions from connected brokers."""
    from datetime import datetime, timezone

    service = PositionsService(db, current_user.id)
    positions = await service.sync_positions()
    return SyncPositionsResponse(
        synced_at=datetime.now(timezone.utc).isoformat(),
        total_positions_synced=len(positions),
    )
