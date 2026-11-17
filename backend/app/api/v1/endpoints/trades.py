"""Trades endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import csv, io
from datetime import date

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.trade import TradeResponse, JournalUpdateRequest
from app.schemas.common import PaginatedResponse
from app.services.trades_service import TradesService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[TradeResponse])
async def get_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    broker_account_id: Optional[int] = None,
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated trade history with optional filters."""
    svc = TradesService(db, current_user.id)
    trades = await svc.get_trades(
        broker_account_id=broker_account_id,
        symbol=symbol,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return PaginatedResponse(
        items=trades,
        total=len(trades),
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_trades(
    broker_account_id: Optional[int] = None,
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export trades as CSV download."""
    svc = TradesService(db, current_user.id)
    trades = await svc.get_trades(
        broker_account_id=broker_account_id,
        symbol=symbol,
        limit=10000,
        offset=0,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Symbol", "Broker", "Side", "Qty", "Price", "Value", "Journal"])
    for t in trades:
        writer.writerow([
            t.trade_timestamp, t.symbol, t.broker_name, t.transaction_type,
            t.quantity, t.price, t.trade_value, t.journal_entry or "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single trade detail."""
    svc = TradesService(db, current_user.id)
    try:
        return await svc.get_trade(trade_id=trade_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{trade_id}/journal", response_model=TradeResponse)
async def update_journal(
    trade_id: int,
    body: JournalUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update trade journal entry and notes."""
    svc = TradesService(db, current_user.id)
    try:
        return await svc.update_journal(trade_id=trade_id, payload=body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
