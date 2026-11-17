"""
Alerts & Telegram Notifications API Endpoints.
"""
from __future__ import annotations

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.config import settings
from app.models.alert import AlertNotification, AlertRule, SignalState
from app.models.user import User
from app.services.alert_service import AlertService
from app.services.telegram_service import TelegramService

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TelegramConfigPayload(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


class AlertRuleCreate(BaseModel):
    name: str = Field(..., example="BTCUSD SuperTrend 16, 1.5 (90m)")
    symbol: str = Field("BTCUSD", example="BTCUSD")
    exchange: str = Field("BINANCE", example="BINANCE")
    timeframe: str = Field("90m", example="90m")
    indicator: str = Field("SUPERTREND", example="SUPERTREND")
    params: dict = Field(default_factory=lambda: {"period": 16, "multiplier": 1.5})
    is_active: bool = True
    notify_telegram: bool = True
    telegram_chat_id: Optional[str] = None


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    params: Optional[dict] = None
    is_active: Optional[bool] = None
    notify_telegram: Optional[bool] = None
    telegram_chat_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Telegram Bot Configuration & Testing
# ---------------------------------------------------------------------------

@router.get("/config")
async def get_telegram_config(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get current Telegram bot configuration status."""
    has_token = bool(settings.TELEGRAM_BOT_TOKEN)
    has_chat_id = bool(settings.TELEGRAM_CHAT_ID)

    bot_info = None
    if has_token:
        info_res = await TelegramService.get_bot_info()
        if info_res.get("success"):
            bot_info = info_res

    return {
        "is_configured": has_token and has_chat_id,
        "has_token": has_token,
        "has_chat_id": has_chat_id,
        "masked_token": f"{settings.TELEGRAM_BOT_TOKEN[:8]}...{settings.TELEGRAM_BOT_TOKEN[-4:]}" if has_token and len(settings.TELEGRAM_BOT_TOKEN) > 12 else ("Set" if has_token else ""),
        "chat_id": settings.TELEGRAM_CHAT_ID or "",
        "bot_info": bot_info,
    }


@router.post("/config")
async def update_telegram_config(
    payload: TelegramConfigPayload,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update Telegram bot token and/or chat ID in runtime settings."""
    if payload.bot_token is not None:
        settings.TELEGRAM_BOT_TOKEN = payload.bot_token.strip()
    if payload.chat_id is not None:
        settings.TELEGRAM_CHAT_ID = payload.chat_id.strip()

    # Try validating with getMe
    bot_info = None
    if settings.TELEGRAM_BOT_TOKEN:
        bot_info = await TelegramService.get_bot_info()

    return {
        "success": True,
        "message": "Telegram settings updated successfully.",
        "has_token": bool(settings.TELEGRAM_BOT_TOKEN),
        "has_chat_id": bool(settings.TELEGRAM_CHAT_ID),
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "bot_info": bot_info,
    }


@router.post("/telegram/test")
async def test_telegram_connection(
    payload: Optional[TelegramConfigPayload] = None,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Send an immediate test alert to verify the Telegram Bot and Chat ID."""
    bot_token = payload.bot_token if payload and payload.bot_token else None
    chat_id = payload.chat_id if payload and payload.chat_id else None

    res = await TelegramService.test_connection(bot_token=bot_token, chat_id=chat_id)
    return res


@router.get("/telegram/detect-chat-id")
async def auto_detect_chat_id(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Auto-detect chat ID from recent messages sent to the bot (e.g. /start)."""
    res = await TelegramService.auto_detect_chat_id()
    if res.get("success") and res.get("chat_id"):
        # Auto set it if current settings chat_id is empty
        if not settings.TELEGRAM_CHAT_ID:
            settings.TELEGRAM_CHAT_ID = res["chat_id"]
    return res


# ---------------------------------------------------------------------------
# Alert Rules CRUD
# ---------------------------------------------------------------------------

@router.get("/rules")
async def list_alert_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    """List all alert rules for the user. Provisions default BTCUSD SuperTrend if none exist."""
    res = await db.execute(
        select(AlertRule)
        .where(AlertRule.user_id == current_user.id)
        .order_by(AlertRule.id.asc())
    )
    rules = res.scalars().all()

    # If no rules exist, create the requested default: BTCUSD SuperTrend (16, 1.5, 90m)
    if not rules:
        default_rule = AlertRule(
            user_id=current_user.id,
            name="BTCUSD SuperTrend 16, 1.5 (90m)",
            symbol="BTCUSD",
            exchange="BINANCE",
            timeframe="90m",
            indicator="SUPERTREND",
            params={"period": 16, "multiplier": 1.5},
            is_active=True,
            notify_telegram=True,
        )
        db.add(default_rule)
        await db.commit()
        await db.refresh(default_rule)

        # Do initial evaluation
        try:
            await AlertService.evaluate_rule(default_rule, db, force_notify=False)
            await db.refresh(default_rule)
        except Exception:
            pass

        rules = [default_rule]

    return [
        {
            "id": r.id,
            "name": r.name,
            "symbol": r.symbol,
            "exchange": r.exchange,
            "timeframe": r.timeframe,
            "indicator": r.indicator,
            "params": r.params,
            "current_signal": r.current_signal,
            "current_value": float(r.current_value) if r.current_value is not None else None,
            "current_spot": float(r.current_spot) if r.current_spot is not None else None,
            "last_flip_at": r.last_flip_at.isoformat() if r.last_flip_at else None,
            "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None,
            "is_active": r.is_active,
            "notify_telegram": r.notify_telegram,
            "telegram_chat_id": r.telegram_chat_id,
        }
        for r in rules
    ]


@router.post("/rules")
async def create_alert_rule(
    payload: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new indicator alert rule."""
    rule = AlertRule(
        user_id=current_user.id,
        name=payload.name,
        symbol=payload.symbol.upper(),
        exchange=payload.exchange.upper(),
        timeframe=payload.timeframe,
        indicator=payload.indicator.upper(),
        params=payload.params,
        is_active=payload.is_active,
        notify_telegram=payload.notify_telegram,
        telegram_chat_id=payload.telegram_chat_id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    # Initial evaluation
    try:
        await AlertService.evaluate_rule(rule, db, force_notify=False)
        await db.refresh(rule)
    except Exception:
        pass

    return {
        "id": rule.id,
        "name": rule.name,
        "symbol": rule.symbol,
        "current_signal": rule.current_signal,
        "current_spot": float(rule.current_spot) if rule.current_spot is not None else None,
        "current_value": float(rule.current_value) if rule.current_value is not None else None,
    }


@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    payload: AlertRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update an existing alert rule."""
    res = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_id, AlertRule.user_id == current_user.id
        )
    )
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    if payload.name is not None:
        rule.name = payload.name
    if payload.symbol is not None:
        rule.symbol = payload.symbol.upper()
    if payload.timeframe is not None:
        rule.timeframe = payload.timeframe
    if payload.params is not None:
        rule.params = payload.params
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.notify_telegram is not None:
        rule.notify_telegram = payload.notify_telegram
    if payload.telegram_chat_id is not None:
        rule.telegram_chat_id = payload.telegram_chat_id

    await db.commit()
    await db.refresh(rule)
    return {"success": True, "rule_id": rule.id, "is_active": rule.is_active}


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete an alert rule."""
    res = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_id, AlertRule.user_id == current_user.id
        )
    )
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await db.delete(rule)
    await db.commit()
    return {"success": True, "deleted_id": rule_id}


@router.post("/rules/{rule_id}/evaluate")
async def evaluate_alert_rule(
    rule_id: int,
    notify: bool = Query(False, description="Force send Telegram notification even if not flipped"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually evaluate rule against live data and optionally force send alert."""
    res = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_id, AlertRule.user_id == current_user.id
        )
    )
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    result = await AlertService.evaluate_rule(rule, db, force_notify=notify)
    return result


@router.get("/live-status")
async def get_live_indicator_status(
    symbol: str = Query("BTCUSD"),
    timeframe: str = Query("90m"),
    period: int = Query(16),
    multiplier: float = Query(1.5),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Live calculation endpoint for any symbol and SuperTrend parameters."""
    try:
        data = await AlertService.get_indicator_status(
            symbol=symbol,
            timeframe=timeframe,
            period=period,
            multiplier=multiplier,
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Notification History Logs
# ---------------------------------------------------------------------------

@router.get("/notifications")
async def list_alert_notifications(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    """List historical alert notifications sent to Telegram."""
    res = await db.execute(
        select(AlertNotification)
        .where(AlertNotification.user_id == current_user.id)
        .order_by(desc(AlertNotification.created_at))
        .limit(limit)
    )
    items = res.scalars().all()
    return [
        {
            "id": n.id,
            "rule_id": n.rule_id,
            "symbol": n.symbol,
            "event_type": n.event_type,
            "old_signal": n.old_signal,
            "new_signal": n.new_signal,
            "spot_price": float(n.spot_price) if n.spot_price is not None else None,
            "indicator_value": float(n.indicator_value) if n.indicator_value is not None else None,
            "message_text": n.message_text,
            "channel": n.channel,
            "status": n.status,
            "error_message": n.error_message,
            "created_at": n.created_at.isoformat(),
        }
        for n in items
    ]
