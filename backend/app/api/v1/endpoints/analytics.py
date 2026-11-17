"""Analytics endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/portfolio-value")
async def get_portfolio_value(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Portfolio value over time for charting."""
    svc = AnalyticsService(db)
    return await svc.get_portfolio_value_history(
        user_id=current_user.id, date_from=date_from, date_to=date_to
    )


@router.get("/xirr")
async def get_xirr(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate portfolio XIRR based on trade history and current value."""
    svc = AnalyticsService(db)
    return await svc.calculate_xirr(user_id=current_user.id)


@router.get("/broker-performance")
async def get_broker_performance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """P&L and return percentage per broker."""
    svc = AnalyticsService(db)
    return await svc.get_broker_performance(user_id=current_user.id)


@router.get("/sector-allocation")
async def get_sector_allocation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Portfolio value grouped by NSE sector."""
    svc = AnalyticsService(db)
    return await svc.get_sector_allocation(user_id=current_user.id)


@router.get("/strategy-performance")
async def get_strategy_performance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """P&L grouped by option strategy type."""
    svc = AnalyticsService(db)
    return await svc.get_strategy_performance(user_id=current_user.id)
