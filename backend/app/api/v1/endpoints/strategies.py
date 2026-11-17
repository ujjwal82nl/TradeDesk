"""Option strategies endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.strategy import OptionStrategy, StrategyStatus
from app.models.broker import BrokerAccount
from app.schemas.strategy import StrategyCreate, StrategyResponse, StrategyLegCreate
from app.services.broker_service import BrokerService

router = APIRouter()

STRATEGY_DESCRIPTIONS = {
    "IRON_FLY": "Sell ATM call + put, buy OTM call + put at equal distance. Max profit at expiry if price stays near strike.",
    "IRON_CONDOR": "Sell OTM call spread + OTM put spread. Profit if price stays within a range.",
    "COVERED_CALL": "Long stock + short OTM call. Generate income from held shares.",
    "SHORT_STRANGLE": "Sell OTM call + OTM put. Profit if price stays between strikes.",
    "SHORT_STRADDLE": "Sell ATM call + ATM put. Max profit if price stays at strike at expiry.",
    "WHEEL": "Sell CSP → if assigned sell CC → repeat cycle to accumulate shares & premium.",
}


@router.get("/types", response_model=List[dict])
async def get_strategy_types():
    """List all supported strategy types with descriptions."""
    return [
        {"type": k, "description": v} for k, v in STRATEGY_DESCRIPTIONS.items()
    ]


@router.get("", response_model=List[StrategyResponse])
async def get_strategies(
    status: Optional[str] = None,
    underlying: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all option strategies for the current user."""
    from sqlalchemy.orm import selectinload
    filters = [BrokerAccount.user_id == current_user.id]
    if status:
        filters.append(OptionStrategy.status == status)
    if underlying:
        filters.append(OptionStrategy.underlying == underlying.upper())

    result = await db.execute(
        select(OptionStrategy)
        .join(BrokerAccount)
        .where(and_(*filters))
        .options(selectinload(OptionStrategy.legs))
        .order_by(OptionStrategy.created_at.desc())
    )
    strategies = result.scalars().all()
    return [_strategy_to_response(s) for s in strategies]


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: StrategyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new option strategy."""
    # Verify broker account belongs to user
    account = await db.get(BrokerAccount, body.broker_account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Broker account not found")

    strategy = OptionStrategy(
        broker_account_id=body.broker_account_id,
        name=body.name,
        strategy_type=body.strategy_type,
        underlying=body.underlying.upper(),
        expiry_date=body.expiry_date,
        status=StrategyStatus.OPEN,
        net_premium=0.0,
        margin_used=0.0,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return _strategy_to_response(strategy)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get strategy detail with all legs."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(OptionStrategy)
        .join(BrokerAccount)
        .where(OptionStrategy.id == strategy_id, BrokerAccount.user_id == current_user.id)
        .options(selectinload(OptionStrategy.legs))
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _strategy_to_response(strategy)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update strategy metadata."""
    result = await db.execute(
        select(OptionStrategy).join(BrokerAccount)
        .where(OptionStrategy.id == strategy_id, BrokerAccount.user_id == current_user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    for k, v in body.items():
        if hasattr(strategy, k):
            setattr(strategy, k, v)
    await db.commit()
    await db.refresh(strategy)
    return _strategy_to_response(strategy)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark strategy as closed."""
    from datetime import datetime, timezone
    result = await db.execute(
        select(OptionStrategy).join(BrokerAccount)
        .where(OptionStrategy.id == strategy_id, BrokerAccount.user_id == current_user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    strategy.status = StrategyStatus.CLOSED
    strategy.closed_at = datetime.now(timezone.utc)
    await db.commit()


def _strategy_to_response(s: OptionStrategy) -> dict:
    from datetime import date
    dte = (s.expiry_date - date.today()).days if s.expiry_date else 0
    legs = []
    current_pnl = 0.0
    if hasattr(s, "legs") and s.legs:
        for leg in s.legs:
            leg_pnl = (leg.current_price - leg.entry_price) * leg.quantity * (
                -1 if leg.transaction_type == "SELL" else 1
            )
            current_pnl += leg_pnl
            legs.append({
                "symbol": leg.symbol, "transaction_type": leg.transaction_type,
                "quantity": leg.quantity, "strike_price": leg.strike_price,
                "option_type": leg.option_type, "expiry_date": leg.expiry_date,
                "entry_price": leg.entry_price, "current_price": leg.current_price,
                "pnl": round(leg_pnl, 2),
            })
    return {
        "id": s.id, "name": s.name, "strategy_type": s.strategy_type,
        "underlying": s.underlying, "expiry_date": s.expiry_date,
        "status": s.status, "max_profit": s.max_profit, "max_loss": s.max_loss,
        "breakeven_lower": s.breakeven_lower, "breakeven_upper": s.breakeven_upper,
        "net_premium": float(s.net_premium or 0), "margin_used": float(s.margin_used or 0),
        "current_pnl": round(current_pnl, 2), "days_to_expiry": max(dte, 0),
        "probability_of_profit": None, "legs": legs,
    }
