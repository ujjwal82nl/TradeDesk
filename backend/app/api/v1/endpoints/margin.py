"""Margin endpoints."""
from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.margin import MarginSummary, MarginResponse
from app.services.margin_service import MarginService

router = APIRouter()


@router.get("", response_model=MarginSummary)
async def get_margin(
    broker_account_id: Optional[int] = Query(None, description="Filter by broker account ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current margin summary across all connected brokers."""
    svc = MarginService(db, current_user.id)
    return await svc.get_current_margin(broker_account_id=broker_account_id)


@router.get("/history", response_model=List[dict])
async def get_margin_history(
    days: int = Query(30, ge=1, le=365),
    broker_account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get historical margin snapshots for charting."""
    svc = MarginService(db, current_user.id)
    date_from = date.today() - timedelta(days=days)
    return await svc.get_margin_history(
        broker_account_id=broker_account_id,
        date_from=date_from,
    )


@router.post("/sync", response_model=MarginSummary)
async def sync_margin(
    broker_account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync margin data from all connected brokers."""
    svc = MarginService(db, current_user.id)
    return await svc.get_current_margin(broker_account_id=broker_account_id)
