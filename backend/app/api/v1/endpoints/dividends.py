"""Dividends endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.dividend import (
    CreateDividendRequest,
    DividendResponse,
    MonthlyIncome,
    StockDividendSummary,
)
from app.schemas.common import PaginatedResponse
from app.services.dividend_service import DividendService

router = APIRouter()


@router.post("", response_model=DividendResponse, status_code=status.HTTP_201_CREATED)
async def create_dividend(
    payload: CreateDividendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually record a received dividend payout."""
    svc = DividendService(db)
    try:
        return await svc.create_dividend(user_id=current_user.id, data=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{dividend_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dividend(
    dividend_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a dividend record."""
    svc = DividendService(db)
    try:
        await svc.delete_dividend(user_id=current_user.id, dividend_id=dividend_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/import-csv")
async def import_dividends_csv(
    file: UploadFile = File(...),
    broker_account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import dividends from CSV/XLSX file (supports Dhan Dividend export and generic CSVs)."""
    svc = DividendService(db)
    try:
        content = await file.read()
        imported = await svc.import_dividends_csv(
            user_id=current_user.id, content_bytes=content, broker_account_id=broker_account_id
        )
        return {"status": "ok", "imported_count": imported}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/sync")
async def sync_dividends(
    broker_account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan connected broker ledgers for dividend credits."""
    svc = DividendService(db)
    synced_count = await svc.sync_dividends_from_broker(
        user_id=current_user.id, broker_account_id=broker_account_id
    )
    return {"status": "ok", "synced_count": synced_count}


@router.get("", response_model=PaginatedResponse[DividendResponse])
async def get_dividends(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    broker_account_id: Optional[int] = None,
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all dividend records with pagination."""
    svc = DividendService(db)
    return await svc.get_dividends(
        user_id=current_user.id, page=page, page_size=page_size,
        broker_account_id=broker_account_id, symbol=symbol,
    )


@router.get("/monthly-income", response_model=List[MonthlyIncome])
async def get_monthly_income(
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get monthly dividend income grouped by month."""
    svc = DividendService(db)
    return await svc.get_monthly_income(user_id=current_user.id, year=year)


@router.get("/annual-income", response_model=List[dict])
async def get_annual_income(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get annual dividend income totals."""
    svc = DividendService(db)
    return await svc.get_annual_income(user_id=current_user.id)


@router.get("/by-stock", response_model=List[StockDividendSummary])
async def get_by_stock(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dividend income grouped by stock."""
    svc = DividendService(db)
    return await svc.get_by_stock(user_id=current_user.id)


@router.get("/by-broker", response_model=List[dict])
async def get_by_broker(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dividend income grouped by broker account."""
    svc = DividendService(db)
    return await svc.get_by_broker(user_id=current_user.id)


@router.get("/calendar", response_model=List[DividendResponse])
async def get_calendar(
    days_ahead: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get upcoming dividend ex-dates and payment dates."""
    svc = DividendService(db)
    return await svc.get_upcoming_calendar(user_id=current_user.id, days_ahead=days_ahead)
