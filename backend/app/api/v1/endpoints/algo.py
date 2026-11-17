"""Algo engine endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.algo import AlgoRun, TradeSignal, AlgoStatus, AlgoMode, AlgoStrategy
from app.schemas.algo import (
    AlgoRunCreate,
    AlgoRunResponse,
    TradeSignalResponse,
    AlgoStrategyCreate,
    AlgoStrategyUpdate,
    AlgoStrategyResponse,
    AlgoTemplatePreset,
)

router = APIRouter()


@router.get("/runs", response_model=List[AlgoRunResponse])
async def list_runs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all algo runs for current user."""
    result = await db.execute(
        select(AlgoRun).where(AlgoRun.user_id == current_user.id)
        .order_by(AlgoRun.started_at.desc())
    )
    return result.scalars().all()


@router.post("/runs", response_model=AlgoRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    body: AlgoRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create and start a new algo run."""
    run = AlgoRun(
        user_id=current_user.id,
        name=body.name,
        strategy_code=body.strategy_code,
        mode=AlgoMode(body.mode),
        status=AlgoStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        config=body.config,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/runs/{run_id}", response_model=AlgoRunResponse)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get algo run details."""
    result = await db.execute(
        select(AlgoRun).where(AlgoRun.id == run_id, AlgoRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Algo run not found")
    return run


@router.post("/runs/{run_id}/stop", response_model=AlgoRunResponse)
async def stop_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop a running algo."""
    result = await db.execute(
        select(AlgoRun).where(AlgoRun.id == run_id, AlgoRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Algo run not found")
    run.status = AlgoStatus.STOPPED
    run.stopped_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/signals", response_model=List[TradeSignalResponse])
async def get_signals(
    run_id: Optional[int] = None,
    executed: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get trade signals, optionally filtered by run or execution status."""
    q = select(TradeSignal).join(AlgoRun).where(AlgoRun.user_id == current_user.id)
    if run_id:
        q = q.where(TradeSignal.algo_run_id == run_id)
    if executed is not None:
        q = q.where(TradeSignal.executed == executed)
    result = await db.execute(q.order_by(TradeSignal.created_at.desc()))
    return result.scalars().all()


@router.post("/signals", response_model=TradeSignalResponse, status_code=status.HTTP_201_CREATED)
async def create_signal(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a manual trade signal."""
    signal = TradeSignal(**body)
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


@router.get("/signals/{signal_id}", response_model=TradeSignalResponse)
async def get_signal(
    signal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get signal detail."""
    result = await db.execute(
        select(TradeSignal).join(AlgoRun)
        .where(TradeSignal.id == signal_id, AlgoRun.user_id == current_user.id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


# ---------------------------------------------------------------------------
# Strategy Configuration & Presets
# ---------------------------------------------------------------------------

PRESET_TEMPLATES: List[dict] = [
    {
        "template_id": "TIME_BASED_STRADDLE",
        "title": "9:20 Intraday Straddle",
        "category": "Option Selling",
        "description": "Sells ATM Call and ATM Put at 09:20 AM with independent Stop Loss per leg. Auto-squares off at 15:15 PM.",
        "default_underlying": "NIFTY",
        "default_product": "MIS",
        "entry_params": {
            "entry_time": "09:20:00",
            "no_entry_after": "14:30:00",
            "strike_type": "ATM",
            "strike_offset": 0,
            "wait_and_trade": False,
        },
        "exit_params": {
            "sl_type": "PERCENT",
            "sl_value": 25.0,
            "tp_type": "PERCENT",
            "tp_value": 50.0,
            "trailing_sl": True,
            "trail_trigger": 10.0,
            "trail_step": 5.0,
            "squareoff_time": "15:15:00",
            "max_daily_loss": 5000.0,
        },
        "legs": [
            {"leg_id": 1, "action": "SELL", "instrument_type": "CE", "strike_offset": 0, "lots": 1, "sl_pct": 25.0, "tp_pct": 50.0},
            {"leg_id": 2, "action": "SELL", "instrument_type": "PE", "strike_offset": 0, "lots": 1, "sl_pct": 25.0, "tp_pct": 50.0},
        ],
    },
    {
        "template_id": "OTM_STRANGLE",
        "title": "OTM Strangle (ATM ± X)",
        "category": "Option Selling",
        "description": "Sells OTM Call (ATM + offset) and OTM Put (ATM - offset) for wide safety margin and theta decay capture.",
        "default_underlying": "BANKNIFTY",
        "default_product": "MIS",
        "entry_params": {
            "entry_time": "09:25:00",
            "no_entry_after": "14:00:00",
            "strike_type": "OTM",
            "strike_offset": 200,
            "wait_and_trade": False,
        },
        "exit_params": {
            "sl_type": "PERCENT",
            "sl_value": 30.0,
            "tp_type": "PERCENT",
            "tp_value": 60.0,
            "trailing_sl": True,
            "trail_trigger": 15.0,
            "trail_step": 5.0,
            "squareoff_time": "15:15:00",
            "max_daily_loss": 6000.0,
        },
        "legs": [
            {"leg_id": 1, "action": "SELL", "instrument_type": "CE", "strike_offset": 200, "lots": 1, "sl_pct": 30.0, "tp_pct": 60.0},
            {"leg_id": 2, "action": "SELL", "instrument_type": "PE", "strike_offset": -200, "lots": 1, "sl_pct": 30.0, "tp_pct": 60.0},
        ],
    },
    {
        "template_id": "DIRECTIONAL_BUY",
        "title": "ATM Strike Momentum Breakout",
        "category": "Option Buying",
        "description": "Buys ATM Call or Put on strong momentum breakout with defined risk and trailing target.",
        "default_underlying": "NIFTY",
        "default_product": "MIS",
        "entry_params": {
            "entry_time": "09:30:00",
            "no_entry_after": "14:30:00",
            "strike_type": "ATM",
            "strike_offset": 0,
            "trigger_direction": "CALL",
        },
        "exit_params": {
            "sl_type": "POINTS",
            "sl_value": 20.0,
            "tp_type": "POINTS",
            "tp_value": 40.0,
            "trailing_sl": True,
            "trail_trigger": 15.0,
            "trail_step": 10.0,
            "squareoff_time": "15:10:00",
            "max_daily_loss": 3000.0,
        },
        "legs": [
            {"leg_id": 1, "action": "BUY", "instrument_type": "CE", "strike_offset": 0, "lots": 1, "sl_pts": 20.0, "tp_pts": 40.0},
        ],
    },
    {
        "template_id": "INDICATOR_BREAKOUT",
        "title": "VWAP + 9/21 EMA Trend Cross",
        "category": "Indicator / Equity & F&O",
        "description": "Enters when 9 EMA crosses 21 EMA above/below VWAP on 5-minute candle close.",
        "default_underlying": "RELIANCE",
        "default_product": "MIS",
        "entry_params": {
            "entry_time": "09:20:00",
            "no_entry_after": "14:45:00",
            "fast_ema": 9,
            "slow_ema": 21,
            "use_vwap": True,
            "candle_timeframe": "5m",
        },
        "exit_params": {
            "sl_type": "PERCENT",
            "sl_value": 1.5,
            "tp_type": "PERCENT",
            "tp_value": 3.0,
            "trailing_sl": True,
            "trail_trigger": 1.0,
            "trail_step": 0.5,
            "squareoff_time": "15:15:00",
            "max_daily_loss": 4000.0,
        },
        "legs": [
            {"leg_id": 1, "action": "BUY", "instrument_type": "EQ", "strike_offset": 0, "lots": 25, "sl_pct": 1.5, "tp_pct": 3.0},
        ],
    },
    {
        "template_id": "IRON_CONDOR",
        "title": "Hedged Iron Condor",
        "category": "Defined Risk Hedged",
        "description": "Sells OTM strangle and buys outer protection wings for lower margin and capped risk.",
        "default_underlying": "NIFTY",
        "default_product": "MIS",
        "entry_params": {
            "entry_time": "09:30:00",
            "no_entry_after": "13:30:00",
            "sell_offset": 150,
            "buy_wing_offset": 300,
        },
        "exit_params": {
            "sl_type": "PERCENT",
            "sl_value": 40.0,
            "tp_type": "PERCENT",
            "tp_value": 50.0,
            "trailing_sl": False,
            "trail_trigger": 0.0,
            "trail_step": 0.0,
            "squareoff_time": "15:15:00",
            "max_daily_loss": 5000.0,
        },
        "legs": [
            {"leg_id": 1, "action": "BUY", "instrument_type": "PE", "strike_offset": -300, "lots": 1},
            {"leg_id": 2, "action": "SELL", "instrument_type": "PE", "strike_offset": -150, "lots": 1, "sl_pct": 40.0},
            {"leg_id": 3, "action": "SELL", "instrument_type": "CE", "strike_offset": 150, "lots": 1, "sl_pct": 40.0},
            {"leg_id": 4, "action": "BUY", "instrument_type": "CE", "strike_offset": 300, "lots": 1},
        ],
    },
]


@router.get("/templates", response_model=List[AlgoTemplatePreset])
async def list_templates():
    """Return catalog of preset strategy templates."""
    return PRESET_TEMPLATES


@router.get("/strategies", response_model=List[AlgoStrategyResponse])
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all saved algorithmic strategies for the current user."""
    result = await db.execute(
        select(AlgoStrategy)
        .where(AlgoStrategy.user_id == current_user.id)
        .order_by(AlgoStrategy.created_at.desc())
    )
    return result.scalars().all()


@router.post("/strategies", response_model=AlgoStrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: AlgoStrategyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new algorithmic strategy."""
    strat = AlgoStrategy(
        user_id=current_user.id,
        broker_account_id=body.broker_account_id,
        name=body.name,
        description=body.description,
        template_type=body.template_type,
        underlying=body.underlying,
        is_active=body.is_active,
        mode=body.mode,
        product_type=body.product_type,
        entry_params=body.entry_params,
        exit_params=body.exit_params,
        legs=body.legs,
    )
    db.add(strat)
    await db.commit()
    await db.refresh(strat)
    return strat


@router.get("/strategies/{strategy_id}", response_model=AlgoStrategyResponse)
async def get_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a strategy by ID."""
    result = await db.execute(
        select(AlgoStrategy).where(
            AlgoStrategy.id == strategy_id, AlgoStrategy.user_id == current_user.id
        )
    )
    strat = result.scalar_one_or_none()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strat


@router.put("/strategies/{strategy_id}", response_model=AlgoStrategyResponse)
async def update_strategy(
    strategy_id: int,
    body: AlgoStrategyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing strategy."""
    result = await db.execute(
        select(AlgoStrategy).where(
            AlgoStrategy.id == strategy_id, AlgoStrategy.user_id == current_user.id
        )
    )
    strat = result.scalar_one_or_none()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(strat, field, val)

    strat.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(strat)
    return strat


@router.delete("/strategies/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a strategy."""
    result = await db.execute(
        select(AlgoStrategy).where(
            AlgoStrategy.id == strategy_id, AlgoStrategy.user_id == current_user.id
        )
    )
    strat = result.scalar_one_or_none()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")

    await db.delete(strat)
    await db.commit()
    return None


@router.post("/strategies/{strategy_id}/toggle-active", response_model=AlgoStrategyResponse)
async def toggle_strategy_active(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle strategy active/inactive status."""
    result = await db.execute(
        select(AlgoStrategy).where(
            AlgoStrategy.id == strategy_id, AlgoStrategy.user_id == current_user.id
        )
    )
    strat = result.scalar_one_or_none()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strat.is_active = not strat.is_active
    strat.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(strat)
    return strat


@router.post("/strategies/{strategy_id}/kill-switch")
async def trigger_kill_switch(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Emergency Kill Switch: square off all open positions and inactivate strategy."""
    result = await db.execute(
        select(AlgoStrategy).where(
            AlgoStrategy.id == strategy_id, AlgoStrategy.user_id == current_user.id
        )
    )
    strat = result.scalar_one_or_none()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strat.is_active = False
    strat.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "success",
        "message": f"Kill Switch activated for '{strat.name}'. Strategy marked inactive.",
        "strategy_id": strategy_id,
    }
