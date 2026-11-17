"""
Portfolio summary and allocation endpoints.

Provides aggregated net-worth, broker/asset allocations, historical snapshots,
and XIRR-based performance metrics across all connected broker accounts.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.portfolio import (
    AssetAllocation,
    BrokerAllocation,
    PortfolioSnapshotResponse,
    PortfolioSummary,
)
from app.services.portfolio_service import PortfolioService
from app.services.analytics_service import AnalyticsService

router = APIRouter()


class PortfolioPerformanceResponse(BaseModel):
    """XIRR and other performance metrics for the portfolio."""

    xirr_pct: Optional[Decimal] = Field(None, description="Annualised XIRR in percent; None if not calculable")
    absolute_return_pct: Decimal = Decimal("0.0")
    cagr_pct: Optional[Decimal] = None
    best_day_pnl: Decimal = Decimal("0.0")
    worst_day_pnl: Decimal = Decimal("0.0")
    inception_date: date = Field(default_factory=date.today)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=PortfolioSummary,
    summary="Aggregated portfolio summary",
)
async def portfolio_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioSummary:
    """
    Return total net worth, overall P&L, and day P&L aggregated
    across all active broker accounts.
    """
    service = PortfolioService(db, current_user.id)
    return await service.get_summary()


@router.get(
    "/broker-allocation",
    response_model=List[BrokerAllocation],
    summary="Broker-wise value allocation",
)
async def broker_allocation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[BrokerAllocation]:
    """
    Break down the current portfolio value by connected broker account,
    including percentage weight for each.
    """
    service = PortfolioService(db, current_user.id)
    return await service.get_broker_allocation()


@router.get(
    "/asset-allocation",
    response_model=List[AssetAllocation],
    summary="Asset class allocation",
)
async def asset_allocation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[AssetAllocation]:
    """
    Break down the portfolio into asset classes (Equity, F&O, Mutual Funds,
    Cash, etc.) with their value and percentage weight.
    """
    service = PortfolioService(db, current_user.id)
    return await service.get_asset_allocation()


@router.get(
    "/snapshots",
    response_model=List[PortfolioSnapshotResponse],
    summary="Historical portfolio value snapshots",
)
async def portfolio_snapshots(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Optional[date] = Query(None, description="Start date (inclusive)"),
    date_to: Optional[date] = Query(None, description="End date (inclusive)"),
) -> List[PortfolioSnapshotResponse]:
    """
    Return time-series snapshots of portfolio value and invested capital
    suitable for charting.
    """
    service = PortfolioService(db, current_user.id)
    return await service.get_snapshots(
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/performance",
    response_model=PortfolioPerformanceResponse,
    summary="Portfolio performance metrics including XIRR",
)
async def portfolio_performance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioPerformanceResponse:
    """
    Compute XIRR (Extended Internal Rate of Return), CAGR, and absolute
    return for the entire portfolio using historical cash-flow data.
    """
    service = AnalyticsService(db)
    xirr_res = await service.calculate_xirr(current_user.id)
    xirr_val = xirr_res.get("xirr")
    return PortfolioPerformanceResponse(
        xirr_pct=Decimal(str(xirr_val)) if xirr_val is not None else None,
        absolute_return_pct=Decimal("0.0"),
        cagr_pct=None,
        best_day_pnl=Decimal("0.0"),
        worst_day_pnl=Decimal("0.0"),
        inception_date=date.today(),
    )
