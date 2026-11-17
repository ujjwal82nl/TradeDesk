"""Analytics service."""
from typing import Optional
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.holding import Holding
from app.models.broker import BrokerAccount, BrokerProvider
from app.models.strategy import OptionStrategy, StrategyStatus


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_portfolio_value_history(
        self, user_id: int, date_from: Optional[date], date_to: Optional[date]
    ) -> list:
        q = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(PortfolioSnapshot.snapshot_date)
        )
        if date_from:
            q = q.where(PortfolioSnapshot.snapshot_date >= date_from)
        if date_to:
            q = q.where(PortfolioSnapshot.snapshot_date <= date_to)
        result = await self.db.execute(q)
        rows = result.scalars().all()
        return [
            {
                "date": str(r.snapshot_date),
                "total_net_worth": float(r.total_net_worth or 0),
                "total_portfolio_value": float(r.total_portfolio_value or 0),
                "today_pnl": float(r.today_pnl or 0),
            }
            for r in rows
        ]

    async def calculate_xirr(self, user_id: int) -> dict:
        """Calculate XIRR using pyxirr based on trade cashflows + current value."""
        try:
            from pyxirr import xirr as _xirr
        except ImportError:
            return {"xirr": None, "message": "pyxirr not installed"}

        # Gather buy/sell cashflows from holdings (simplified)
        # Real implementation would use full trade history
        result = await self.db.execute(
            select(
                func.sum(Holding.average_cost * Holding.quantity).label("invested"),
                func.sum(Holding.current_value).label("current"),
            )
            .join(BrokerAccount)
            .where(BrokerAccount.user_id == user_id)
        )
        row = result.one()
        invested = float(row.invested or 0)
        current = float(row.current or 0)

        if invested == 0:
            return {"xirr": None, "message": "No holdings data"}

        # Simplified: return IRR based on single cashflow pair
        simple_return = (current - invested) / invested * 100
        return {
            "xirr": round(simple_return, 2),
            "total_invested": round(invested, 2),
            "current_value": round(current, 2),
            "absolute_return": round(current - invested, 2),
            "message": "Simplified return; full XIRR requires complete trade history",
        }

    async def get_broker_performance(self, user_id: int) -> list:
        result = await self.db.execute(
            select(
                BrokerProvider.display_name,
                func.sum(Holding.current_value).label("current_value"),
                func.sum(Holding.average_cost * Holding.quantity).label("invested"),
                func.sum(Holding.pnl).label("pnl"),
            )
            .join(BrokerAccount, Holding.broker_account_id == BrokerAccount.id)
            .join(BrokerProvider, BrokerAccount.broker_id == BrokerProvider.id)
            .where(BrokerAccount.user_id == user_id)
            .group_by(BrokerProvider.display_name)
        )
        rows = result.all()
        return [
            {
                "broker": r.display_name,
                "current_value": float(r.current_value or 0),
                "invested": float(r.invested or 0),
                "pnl": float(r.pnl or 0),
                "return_percent": round(float(r.pnl or 0) / max(float(r.invested or 1), 1) * 100, 2),
            }
            for r in rows
        ]

    async def get_sector_allocation(self, user_id: int) -> list:
        """Return sector allocation. Sector data requires external mapping (NSE)."""
        result = await self.db.execute(
            select(Holding.symbol, func.sum(Holding.current_value).label("value"))
            .join(BrokerAccount)
            .where(BrokerAccount.user_id == user_id)
            .group_by(Holding.symbol)
            .order_by(func.sum(Holding.current_value).desc())
        )
        rows = result.all()
        total = sum(float(r.value or 0) for r in rows)
        return [
            {
                "symbol": r.symbol,
                "sector": "Unknown",  # Requires NSE sector mapping integration
                "value": float(r.value or 0),
                "percentage": round(float(r.value or 0) / max(total, 1) * 100, 2),
            }
            for r in rows
        ]

    async def get_strategy_performance(self, user_id: int) -> list:
        result = await self.db.execute(
            select(
                OptionStrategy.strategy_type,
                func.count(OptionStrategy.id).label("count"),
                func.sum(OptionStrategy.net_premium).label("total_premium"),
            )
            .join(BrokerAccount)
            .where(BrokerAccount.user_id == user_id)
            .group_by(OptionStrategy.strategy_type)
        )
        rows = result.all()
        return [
            {
                "strategy_type": r.strategy_type,
                "count": r.count,
                "total_premium": float(r.total_premium or 0),
            }
            for r in rows
        ]
