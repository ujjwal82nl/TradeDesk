"""
PortfolioService: aggregate portfolio metrics across all broker adapters.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import BrokerAccount
from app.models.holding import Holding
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.schemas.portfolio import (
    AssetAllocation,
    BrokerAllocation,
    PortfolioSnapshotResponse,
    PortfolioSummary,
)
from app.services.broker_service import BrokerService

logger = logging.getLogger(__name__)


class PortfolioService:
    """Aggregates holdings, positions, and cash from all linked brokers."""

    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self._db = db
        self._user_id = user_id
        self._broker_service = BrokerService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_summary(self, record_snapshot: bool = True) -> PortfolioSummary:
        """
        Fetch live data from all active broker adapters and produce an
        aggregated PortfolioSummary.

        Individual broker failures are logged but do not abort the summary;
        the broker is silently excluded from aggregation.
        """
        accounts = await self._broker_service.get_user_accounts(self._user_id)
        broker_data = await self._fetch_all_brokers(accounts)

        total_portfolio_value = sum(d.get("portfolio_value", 0.0) for d in broker_data)
        total_cash = sum(d.get("cash", 0.0) for d in broker_data)
        total_net_worth = total_portfolio_value + total_cash
        today_pnl = sum(d.get("today_pnl", 0.0) for d in broker_data)
        prev_close_value = total_net_worth - today_pnl
        today_pnl_percent = (
            (today_pnl / prev_close_value * 100) if prev_close_value else 0.0
        )

        summary = PortfolioSummary(
            total_net_worth=total_net_worth,
            total_portfolio_value=total_portfolio_value,
            today_pnl=today_pnl,
            today_pnl_percent=today_pnl_percent,
            unrealized_pnl=sum(d.get("unrealized_pnl", 0.0) for d in broker_data),
            realized_pnl=sum(d.get("realized_pnl", 0.0) for d in broker_data),
            total_cash=total_cash,
            total_margin_used=sum(d.get("margin_used", 0.0) for d in broker_data),
            broker_count=len(broker_data),
            last_updated=datetime.utcnow(),
        )

        if record_snapshot and total_net_worth > 0:
            try:
                await self.save_snapshot(summary)
            except Exception:
                logger.exception("Failed to auto-save snapshot")

        return summary

    async def get_broker_allocation(self) -> List[BrokerAllocation]:
        """Return portfolio value broken down by broker."""
        accounts = await self._broker_service.get_user_accounts(self._user_id)
        broker_data = await self._fetch_all_brokers(accounts)

        total_value = sum(d.get("portfolio_value", 0.0) for d in broker_data)
        allocations: List[BrokerAllocation] = []

        for account, data in zip(accounts, broker_data):
            value = data.get("portfolio_value", 0.0)
            allocations.append(
                BrokerAllocation(
                    broker_name=account.account_name,
                    value=value,
                    percentage=(value / total_value * 100) if total_value else 0.0,
                    cash=data.get("cash", 0.0),
                )
            )
        return allocations

    async def get_asset_allocation(self) -> List[AssetAllocation]:
        """
        Return portfolio value broken down by asset/instrument type.

        Aggregates across all brokers; relies on holdings returning an
        ``instrument_type`` field per position.
        """
        accounts = await self._broker_service.get_user_accounts(self._user_id)
        type_totals: Dict[str, float] = {}

        async def _fetch_holdings(acc: BrokerAccount) -> None:
            try:
                adapter = await self._broker_service.get_broker_instance(
                    acc.id, self._user_id
                )
                holdings = await adapter.get_holdings()
                if holdings:
                    for h in holdings:
                        itype = getattr(h, "instrument_type", "EQ") or "EQ"
                        val = getattr(h, "current_value", None)
                        if val is None:
                            val = (getattr(h, "quantity", 0) or 0) * (getattr(h, "current_price", 0.0) or 0.0)
                        type_totals[itype] = type_totals.get(itype, 0.0) + float(val or 0.0)
                    return
            except Exception:
                logger.warning("Asset allocation live fetch failed for account %s", acc.id)

            try:
                stmt = select(Holding).where(Holding.broker_account_id == acc.id)
                res = await self._db.execute(stmt)
                for h in res.scalars().all():
                    itype = h.instrument_type or "EQ"
                    type_totals[itype] = type_totals.get(itype, 0.0) + float(h.current_value or 0.0)
            except Exception:
                pass

        await asyncio.gather(*[_fetch_holdings(acc) for acc in accounts])

        grand_total = sum(type_totals.values())
        return [
            AssetAllocation(
                asset_type=atype,
                value=value,
                percentage=(value / grand_total * 100) if grand_total else 0.0,
            )
            for atype, value in sorted(type_totals.items())
        ]

    async def save_snapshot(
        self, summary: Optional[PortfolioSummary] = None
    ) -> PortfolioSnapshot:
        """
        Compute a fresh summary and persist an end-of-day snapshot row.

        If a snapshot for today already exists it is updated in-place.
        """
        if summary is None:
            summary = await self.get_summary(record_snapshot=False)
        today = date.today()

        stmt = select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == self._user_id,
            PortfolioSnapshot.snapshot_date == today,
        )
        result = await self._db.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot:
            snapshot.total_net_worth = Decimal(str(summary.total_net_worth))
            snapshot.total_portfolio_value = Decimal(str(summary.total_portfolio_value))
            snapshot.today_pnl = Decimal(str(summary.today_pnl))
            snapshot.unrealized_pnl = Decimal(str(summary.unrealized_pnl))
            snapshot.realized_pnl = Decimal(str(summary.realized_pnl))
            snapshot.total_cash = Decimal(str(summary.total_cash))
            snapshot.total_margin_used = Decimal(str(summary.total_margin_used))
        else:
            snapshot = PortfolioSnapshot(
                user_id=self._user_id,
                snapshot_date=today,
                total_net_worth=Decimal(str(summary.total_net_worth)),
                total_portfolio_value=Decimal(str(summary.total_portfolio_value)),
                today_pnl=Decimal(str(summary.today_pnl)),
                unrealized_pnl=Decimal(str(summary.unrealized_pnl)),
                realized_pnl=Decimal(str(summary.realized_pnl)),
                total_cash=Decimal(str(summary.total_cash)),
                total_margin_used=Decimal(str(summary.total_margin_used)),
            )
            self._db.add(snapshot)

        await self._db.commit()
        await self._db.refresh(snapshot)
        return snapshot

    async def get_snapshots(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> List[PortfolioSnapshotResponse]:
        """Return historical EOD snapshots for the trend chart."""
        stmt = select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == self._user_id
        )
        if date_from:
            stmt = stmt.where(PortfolioSnapshot.snapshot_date >= date_from)
        if date_to:
            stmt = stmt.where(PortfolioSnapshot.snapshot_date <= date_to)
        stmt = stmt.order_by(PortfolioSnapshot.snapshot_date)
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        return [PortfolioSnapshotResponse.model_validate(r) for r in rows]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _fetch_all_brokers(
        self, accounts: List[BrokerAccount]
    ) -> List[Dict[str, Any]]:
        """Fan out to all broker adapters concurrently; return partial results."""

        async def _safe_fetch(acc: BrokerAccount) -> Dict[str, Any]:
            portfolio_val = 0.0
            unrealized_pnl = 0.0
            today_pnl = 0.0
            realized_pnl = 0.0
            cash = 0.0
            margin_used = 0.0
            live_holdings_found = False

            try:
                adapter = await self._broker_service.get_broker_instance(
                    acc.id, self._user_id
                )

                # 1. Fetch live holdings to calculate portfolio equity value and P&L
                try:
                    holdings = await adapter.get_holdings()
                    if holdings:
                        live_holdings_found = True
                        for h in holdings:
                            val = getattr(h, "current_value", None)
                            if val is None:
                                qty = getattr(h, "quantity", 0) or 0
                                price = getattr(h, "current_price", 0.0) or getattr(h, "average_price", 0.0) or 0.0
                                val = qty * price
                            portfolio_val += float(val or 0.0)
                            unrealized_pnl += float(getattr(h, "pnl", 0.0) or 0.0)
                            today_pnl += float(getattr(h, "day_change", 0.0) or 0.0)
                except Exception:
                    logger.warning("Live holdings fetch failed for account %s", acc.id)

                # 2. Fetch live funds
                try:
                    funds = await adapter.get_funds()
                    fd = funds.model_dump() if hasattr(funds, "model_dump") else funds
                    cash = float(fd.get("available_margin", fd.get("cash_balance", 0.0)) or 0.0)
                    margin_used = float(fd.get("used_margin", fd.get("utilized_amount", 0.0)) or 0.0)
                except Exception:
                    logger.warning("Live funds fetch failed for account %s", acc.id)

                # 3. Fetch live positions for intraday P&Ls
                try:
                    positions = await adapter.get_positions()
                    for p in positions:
                        unrealized_pnl += float(getattr(p, "unrealized_pnl", getattr(p, "pnl", 0.0)) or 0.0)
                        realized_pnl += float(getattr(p, "realized_pnl", 0.0) or 0.0)
                except Exception:
                    pass

            except Exception:
                logger.exception("Failed to initialize broker adapter for account %s", acc.id)

            # 4. Fallback to local DB cached holdings if live holdings were not retrieved
            if not live_holdings_found or portfolio_val == 0.0:
                try:
                    stmt = select(Holding).where(Holding.broker_account_id == acc.id)
                    res = await self._db.execute(stmt)
                    db_holdings = res.scalars().all()
                    if db_holdings:
                        db_val = sum(
                            float(h.current_value or (h.quantity * (h.current_price or h.average_cost or 0.0)))
                            for h in db_holdings
                        )
                        if db_val > 0:
                            portfolio_val = db_val
                            unrealized_pnl = sum(float(h.pnl or 0.0) for h in db_holdings)
                            today_pnl = sum(float(h.day_change or 0.0) for h in db_holdings)
                except Exception:
                    logger.exception("Database fallback failed for account %s", acc.id)

            return {
                "portfolio_value": portfolio_val,
                "cash": cash,
                "today_pnl": today_pnl,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": realized_pnl,
                "margin_used": margin_used,
                "broker_name": acc.account_name,
            }

        results = await asyncio.gather(*[_safe_fetch(acc) for acc in accounts])
        return [r for r in results if r]
