"""
Holdings endpoints.

Supports listing raw and symbol-merged holdings across all connected brokers,
per-symbol drill-down, and manual sync.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.holding import (
    HoldingLotsResponse,
    HoldingResponse,
    MergedHoldingResponse,
)
from app.services.holdings_service import HoldingsService

router = APIRouter()


class SyncHoldingsResponse(BaseModel):
    """Result of a holdings sync operation."""

    synced_at: str
    total_holdings_synced: int = 0
    broker_results: dict = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[HoldingResponse],
    summary="All holdings across brokers",
)
async def list_holdings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    broker_account_id: Optional[int] = Query(None, description="Filter by broker account ID"),
) -> List[HoldingResponse]:
    """List all holdings for the current user."""
    service = HoldingsService(db, current_user.id)
    return await service.get_all_holdings(broker_account_id=broker_account_id)


@router.get(
    "/merged",
    response_model=List[MergedHoldingResponse],
    summary="Symbol-merged view of holdings across all brokers",
)
async def merged_holdings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[MergedHoldingResponse]:
    """Aggregate holdings by symbol across all brokers."""
    service = HoldingsService(db, current_user.id)
    return await service.get_merged_holdings()


@router.get(
    "/{holding_id}/lots",
    response_model=HoldingLotsResponse,
    summary="Trade lots / historical creation breakdown for a holding",
)
async def holding_lots(
    holding_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    force_refresh: bool = Query(False, description="Force re-syncing trade history from broker"),
) -> HoldingLotsResponse:
    """Return historical open buy trades (tax lots) for the given holding."""
    service = HoldingsService(db, current_user.id)
    try:
        return await service.get_holding_lots(holding_id, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/lots/by-symbol/{symbol}",
    response_model=List[HoldingLotsResponse],
    summary="Trade lots by symbol across all holding accounts",
)
async def lots_by_symbol(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    force_refresh: bool = Query(False, description="Force re-syncing trade history from broker"),
) -> List[HoldingLotsResponse]:
    """Return historical trade lots for all holdings matching symbol."""
    service = HoldingsService(db, current_user.id)
    return await service.get_lots_by_symbol(symbol, force_refresh=force_refresh)


@router.get(
    "/{symbol}",
    response_model=List[HoldingResponse],
    summary="Holdings for a specific symbol across all brokers",
)
async def holdings_by_symbol(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[HoldingResponse]:
    """Return every holding record for the given symbol."""
    service = HoldingsService(db, current_user.id)
    all_h = await service.get_all_holdings()
    matched = [h for h in all_h if h.symbol.upper() == symbol.upper()]
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No holdings found for symbol '{symbol}'.",
        )
    return matched


@router.post(
    "/sync",
    response_model=SyncHoldingsResponse,
    summary="Sync holdings from all brokers",
)
async def sync_holdings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyncHoldingsResponse:
    """Pull the latest holdings from connected broker accounts."""
    from datetime import datetime, timezone

    service = HoldingsService(db, current_user.id)
    holdings = await service.sync_holdings()
    return SyncHoldingsResponse(
        synced_at=datetime.now(timezone.utc).isoformat(),
        total_holdings_synced=len(holdings),
    )
