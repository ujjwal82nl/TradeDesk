"""
PositionsService: intraday/overnight positions with optional greeks calculation.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import BrokerAccount
from app.models.position import Position
from app.schemas.position import GreeksSummary, OptionPositionResponse, PositionResponse
from app.services.broker_service import BrokerService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simplified Black-Scholes greeks (no external dependency required)
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
) -> dict:
    """
    Compute Black-Scholes greeks for a European option.

    Args:
        S: Current spot price of the underlying.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate (e.g. 0.07 for 7 %).
        sigma: Implied volatility (e.g. 0.20 for 20 %).
        option_type: 'CE' or 'PE'.

    Returns:
        dict with keys delta, gamma, theta, vega.
    """
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * _norm_pdf(d1) * math.sqrt(T) / 100  # per 1 % IV move

    if option_type.upper() == "CE":
        delta = _norm_cdf(d1)
        theta = (
            -(S * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * _norm_cdf(d2)
        ) / 365
    else:  # PE
        delta = _norm_cdf(d1) - 1
        theta = (
            -(S * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * _norm_cdf(-d2)
        ) / 365

    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PositionsService:
    """Application-layer service for open trading positions."""

    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self._db = db
        self._user_id = user_id
        self._broker_svc = BrokerService(db)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_all_positions(
        self,
        broker_account_id: Optional[int] = None,
    ) -> List[PositionResponse]:
        """Return all persisted positions for the user."""
        stmt = (
            select(Position)
            .options(selectinload(Position.broker_account).selectinload(BrokerAccount.broker))
            .join(BrokerAccount, Position.broker_account_id == BrokerAccount.id)
            .where(BrokerAccount.user_id == self._user_id)
        )
        if broker_account_id is not None:
            stmt = stmt.where(Position.broker_account_id == broker_account_id)

        result = await self._db.execute(stmt.order_by(Position.symbol))
        positions = result.scalars().all()
        return [PositionResponse.model_validate(p) for p in positions]

    async def get_option_positions(
        self,
        underlying: Optional[str] = None,
        broker_account_id: Optional[int] = None,
        risk_free_rate: float = 0.07,
        implied_volatility: float = 0.15,
    ) -> List[OptionPositionResponse]:
        """
        Return option positions enriched with Black-Scholes greeks.

        Args:
            underlying: Filter to a specific underlying (e.g. 'NIFTY').
            broker_account_id: Filter to a specific broker account.
            risk_free_rate: Annual risk-free rate for greeks computation.
            implied_volatility: Flat IV assumption when live IV is unavailable.
        """
        stmt = (
            select(Position)
            .options(selectinload(Position.broker_account).selectinload(BrokerAccount.broker))
            .join(BrokerAccount, Position.broker_account_id == BrokerAccount.id)
            .where(
                BrokerAccount.user_id == self._user_id,
                Position.instrument_type == "OPT",
            )
        )
        if underlying:
            stmt = stmt.where(Position.underlying == underlying)
        if broker_account_id is not None:
            stmt = stmt.where(Position.broker_account_id == broker_account_id)

        result = await self._db.execute(stmt)
        positions = result.scalars().all()

        enriched: List[OptionPositionResponse] = []
        today = date.today()
        for pos in positions:
            greeks: dict = {}
            if pos.delta is not None:
                greeks = {
                    "delta": float(pos.delta),
                    "gamma": float(pos.gamma) if pos.gamma is not None else 0.0,
                    "theta": float(pos.theta) if pos.theta is not None else 0.0,
                    "vega": float(pos.vega) if pos.vega is not None else 0.0,
                }
            elif pos.expiry_date and pos.strike_price and pos.option_type:
                T = max((pos.expiry_date - today).days, 0) / 365.0
                greeks = _bs_greeks(
                    S=float(pos.last_price or 0.0),
                    K=float(pos.strike_price or 0.0),
                    T=T,
                    r=risk_free_rate,
                    sigma=implied_volatility,
                    option_type=pos.option_type,
                )

            enriched.append(
                OptionPositionResponse(
                    **PositionResponse.model_validate(pos).model_dump(),
                    **greeks,
                )
            )
        return enriched

    async def calculate_greeks_summary(
        self,
        underlying: Optional[str] = None,
    ) -> GreeksSummary:
        """Compute net portfolio-level greeks across all option positions."""
        option_positions = await self.get_option_positions(underlying=underlying)

        net_delta = net_theta = net_vega = net_gamma = 0.0
        for pos in option_positions:
            qty = pos.quantity  # positive=long, negative=short
            net_delta += (pos.delta or 0.0) * qty
            net_theta += (pos.theta or 0.0) * qty
            net_vega += (pos.vega or 0.0) * qty
            net_gamma += (pos.gamma or 0.0) * qty

        return GreeksSummary(
            net_delta=net_delta,
            net_theta=net_theta,
            net_vega=net_vega,
            net_gamma=net_gamma,
            total_positions=len(option_positions),
        )

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync_positions(self, broker_account_id: Optional[int] = None) -> List[Position]:
        """Sync positions from all (or specific) broker accounts."""
        accounts = await self._broker_svc.get_user_accounts(self._user_id)
        if broker_account_id is not None:
            accounts = [a for a in accounts if a.id == broker_account_id]
        all_positions: List[Position] = []
        for acc in accounts:
            try:
                p = await self.sync_positions_from_broker(acc.id)
                all_positions.extend(p)
            except Exception as exc:
                logger.warning(
                    "sync_positions: failed for broker account %s (%s): %s",
                    acc.id,
                    acc.account_name,
                    exc,
                )
        return all_positions

    async def sync_positions_from_broker(self, broker_account_id: int) -> List[Position]:
        """
        Pull the latest positions from the broker API and upsert into the DB.

        Positions no longer returned by the broker (closed) have their
        quantity set to 0.

        Returns:
            The refreshed list of Position ORM objects.
        """
        adapter = await self._broker_svc.get_broker_instance(
            broker_account_id, self._user_id
        )
        raw_positions: List[dict] = await adapter.get_positions()

        stmt = select(Position).where(Position.broker_account_id == broker_account_id)
        result = await self._db.execute(stmt)
        existing: Dict[str, Position] = {
            f"{p.symbol}_{p.product_type}": p for p in result.scalars().all()
        }

        seen_keys: set[str] = set()
        updated: List[Position] = []

        for item in raw_positions:
            raw = item.model_dump() if hasattr(item, "model_dump") else item
            symbol: str = raw.get("symbol", "")
            product_type: str = raw.get("product_type", "")
            if not symbol:
                continue
            key = f"{symbol}_{product_type}"
            seen_keys.add(key)

            if key in existing:
                pos = existing[key]
            else:
                pos = Position(broker_account_id=broker_account_id, symbol=symbol)
                self._db.add(pos)

            pos.symbol = symbol
            pos.exchange = raw.get("exchange", "")
            pos.product_type = product_type
            pos.instrument_type = raw.get("instrument_type", "EQ")
            pos.quantity = float(raw.get("quantity") if raw.get("quantity") is not None else raw.get("net_qty", 0))
            pos.buy_quantity = float(raw.get("buy_qty", 0))
            pos.sell_quantity = float(raw.get("sell_qty", 0))
            pos.average_price = float(raw.get("average_price") if raw.get("average_price") is not None else raw.get("buy_avg", 0))
            pos.last_price = float(raw.get("last_price", 0))
            pos.pnl = float(raw.get("pnl") if raw.get("pnl") is not None else raw.get("realized_profit", 0))
            pos.day_pnl = float(raw.get("day_pnl") if raw.get("day_pnl") is not None else raw.get("unrealized_profit", 0))
            pos.multiplier = float(raw.get("multiplier", 1.0) or 1.0)
            exp_val = raw.get("expiry_date")
            if hasattr(exp_val, "date"):
                exp_val = exp_val.date()
            pos.expiry_date = exp_val
            pos.strike_price = raw.get("strike_price")
            pos.option_type = raw.get("option_type")
            pos.lot_size = int(raw.get("lot_size", 1))
            pos.delta = float(raw.get("delta")) if raw.get("delta") is not None else None
            pos.gamma = float(raw.get("gamma")) if raw.get("gamma") is not None else None
            pos.theta = float(raw.get("theta")) if raw.get("theta") is not None else None
            pos.vega = float(raw.get("vega")) if raw.get("vega") is not None else None
            pos.last_updated = datetime.utcnow()
            updated.append(pos)

        # Remove positions that were not traded in today's session
        for key, pos in existing.items():
            if key not in seen_keys:
                await self._db.delete(pos)

        await self._db.commit()
        return updated
