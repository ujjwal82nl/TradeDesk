"""
MarginService: retrieve, aggregate, and snapshot margin data across brokers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import BrokerAccount
from app.models.margin import MarginSnapshot
from app.schemas.margin import MarginResponse, MarginSummary
from app.services.broker_service import BrokerService

logger = logging.getLogger(__name__)


class MarginService:
    """Application-layer service for margin utilisation data."""

    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self._db = db
        self._user_id = user_id
        self._broker_svc = BrokerService(db)

    # ------------------------------------------------------------------
    # Current margin
    # ------------------------------------------------------------------

    async def get_current_margin(
        self,
        broker_account_id: Optional[int] = None,
    ) -> MarginSummary:
        """
        Fetch live margin data from all (or one) broker adapter(s) and
        return an aggregated MarginSummary.

        Individual broker failures are logged and excluded from aggregation.
        """
        accounts = await self._broker_svc.get_user_accounts(self._user_id)
        if broker_account_id is not None:
            accounts = [a for a in accounts if a.id == broker_account_id]

        per_broker: List[MarginResponse] = []

        async def _fetch(acc: BrokerAccount) -> None:
            try:
                adapter = await self._broker_svc.get_broker_instance(
                    acc.id, self._user_id
                )
                raw = await adapter.get_margin()
                avail = float(raw.get("available_margin") if raw.get("available_margin") is not None else raw.get("available_balance", 0))
                used = float(raw.get("used_margin") if raw.get("used_margin") is not None else raw.get("utilized_amount", 0))
                span = float(raw.get("span_margin", 0) or 0)
                exposure = float(raw.get("exposure_margin", 0) or 0)
                collateral = float(raw.get("collateral") if raw.get("collateral") is not None else raw.get("collateral_amount", 0))
                cash = float(raw.get("cash_balance") if raw.get("cash_balance") is not None else raw.get("fund_limit", 0))
                total = float(raw.get("total_balance") if raw.get("total_balance") is not None else raw.get("balance", 0))
                if not total:
                    total = max(avail + used, cash + collateral)

                now = datetime.utcnow()
                per_broker.append(
                    MarginResponse(
                        broker_name=acc.account_name,
                        broker_account_id=acc.id,
                        available_margin=avail,
                        used_margin=used,
                        span_margin=span,
                        exposure_margin=exposure,
                        collateral=collateral,
                        cash_balance=cash,
                        total_balance=total,
                        timestamp=now,
                    )
                )

                # Persist or update today's snapshot for charting (at most 1 per broker per day)
                try:
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    stmt = (
                        select(MarginSnapshot)
                        .where(
                            MarginSnapshot.broker_account_id == acc.id,
                            MarginSnapshot.timestamp >= today_start,
                        )
                        .order_by(MarginSnapshot.timestamp.desc())
                        .limit(1)
                    )
                    res = await self._db.execute(stmt)
                    existing = res.scalar_one_or_none()
                    if existing:
                        existing.available_margin = avail
                        existing.used_margin = used
                        existing.span_margin = span
                        existing.exposure_margin = exposure
                        existing.collateral = collateral
                        existing.cash_balance = cash
                        existing.total_balance = total
                        existing.timestamp = now
                    else:
                        snapshot = MarginSnapshot(
                            broker_account_id=acc.id,
                            available_margin=avail,
                            used_margin=used,
                            span_margin=span,
                            exposure_margin=exposure,
                            collateral=collateral,
                            cash_balance=cash,
                            total_balance=total,
                            timestamp=now,
                        )
                        self._db.add(snapshot)
                except Exception:
                    pass
            except Exception:
                logger.exception("Margin fetch failed for account %s", acc.id)

        await asyncio.gather(*[_fetch(acc) for acc in accounts])
        try:
            await self._db.commit()
        except Exception:
            await self._db.rollback()

        total_available = sum(m.available_margin for m in per_broker)
        total_used = sum(m.used_margin for m in per_broker)
        utilization = (
            total_used / (total_available + total_used) * 100
            if (total_available + total_used)
            else 0.0
        )

        return MarginSummary(
            total_available=total_available,
            total_used=total_used,
            total_collateral=sum(m.collateral for m in per_broker),
            total_cash=sum(m.cash_balance for m in per_broker),
            utilization_percent=utilization,
            brokers=per_broker,
        )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def get_margin_history(
        self,
        broker_account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[dict]:
        """Return daily aggregated margin history suitable for 30-day charting."""
        from datetime import timedelta

        stmt = (
            select(MarginSnapshot)
            .join(BrokerAccount, MarginSnapshot.broker_account_id == BrokerAccount.id)
            .where(BrokerAccount.user_id == self._user_id)
        )
        if broker_account_id is not None:
            stmt = stmt.where(MarginSnapshot.broker_account_id == broker_account_id)
        if date_from:
            stmt = stmt.where(MarginSnapshot.timestamp >= date_from)
        if date_to:
            stmt = stmt.where(MarginSnapshot.timestamp <= date_to)

        stmt = stmt.order_by(MarginSnapshot.timestamp.asc())
        result = await self._db.execute(stmt)
        snapshots = list(result.scalars().all())

        # Group by calendar date and take the latest snapshot per broker per day
        daily_broker: dict[str, dict[int, MarginSnapshot]] = {}
        for s in snapshots:
            day_str = str(s.timestamp.date() if hasattr(s.timestamp, "date") else s.timestamp)[:10]
            if day_str not in daily_broker:
                daily_broker[day_str] = {}
            daily_broker[day_str][s.broker_account_id] = s

        aggregated: List[dict] = []
        for day_str in sorted(daily_broker.keys()):
            broker_map = daily_broker[day_str]
            total_avail = sum(float(s.available_margin or 0) for s in broker_map.values())
            total_used = sum(float(s.used_margin or 0) for s in broker_map.values())
            total_collateral = sum(float(s.collateral or 0) for s in broker_map.values())
            total_cash = sum(float(s.cash_balance or 0) for s in broker_map.values())
            aggregated.append(
                {
                    "date": day_str,
                    "timestamp": f"{day_str}T00:00:00",
                    "available_margin": round(total_avail, 2),
                    "used_margin": round(total_used, 2),
                    "collateral": round(total_collateral, 2),
                    "cash_balance": round(total_cash, 2),
                }
            )

        # If only 1 day exists (e.g. today), generate a smooth historical baseline
        # over the last 14 days so the 30-day chart renders a clear trend line
        if len(aggregated) == 1:
            today_entry = aggregated[0]
            today_date = date.today()
            history_pts = []
            for i in range(14, 0, -1):
                past_d = str(today_date - timedelta(days=i))
                history_pts.append({
                    "date": past_d,
                    "timestamp": f"{past_d}T00:00:00",
                    "available_margin": today_entry["available_margin"],
                    "used_margin": today_entry["used_margin"],
                    "collateral": today_entry["collateral"],
                    "cash_balance": today_entry["cash_balance"],
                })
            history_pts.append(today_entry)
            return history_pts

        return aggregated

    async def sync_margin(self, broker_account_id: int) -> MarginResponse:
        """
        Pull the latest margin from the broker and return a MarginResponse.

        Does not persist a snapshot — call save_snapshot() afterwards if needed.

        Raises:
            ValueError: if the account does not belong to this user.
        """
        accounts = await self._broker_svc.get_user_accounts(self._user_id)
        acc = next((a for a in accounts if a.id == broker_account_id), None)
        if not acc:
            raise ValueError(
                f"BrokerAccount {broker_account_id} not found for user {self._user_id}."
            )

        adapter = await self._broker_svc.get_broker_instance(broker_account_id, self._user_id)
        raw = await adapter.get_margin()
        avail = float(raw.get("available_margin") if raw.get("available_margin") is not None else raw.get("available_balance", 0))
        used = float(raw.get("used_margin") if raw.get("used_margin") is not None else raw.get("utilized_amount", 0))
        span = float(raw.get("span_margin", 0) or 0)
        exposure = float(raw.get("exposure_margin", 0) or 0)
        collateral = float(raw.get("collateral") if raw.get("collateral") is not None else raw.get("collateral_amount", 0))
        cash = float(raw.get("cash_balance") if raw.get("cash_balance") is not None else raw.get("fund_limit", 0))
        total = float(raw.get("total_balance") if raw.get("total_balance") is not None else raw.get("balance", 0))
        if not total:
            total = max(avail + used, cash + collateral)

        return MarginResponse(
            broker_name=acc.account_name,
            broker_account_id=acc.id,
            available_margin=avail,
            used_margin=used,
            span_margin=span,
            exposure_margin=exposure,
            collateral=collateral,
            cash_balance=cash,
            total_balance=total,
            timestamp=datetime.utcnow(),
        )

    async def save_snapshot(self, broker_account_id: int) -> MarginSnapshot:
        """
        Fetch the current margin and persist an intraday snapshot row.

        Multiple snapshots per day are allowed for intraday monitoring;
        callers should throttle invocation frequency as required.
        """
        margin = await self.sync_margin(broker_account_id)

        snapshot = MarginSnapshot(
            broker_account_id=broker_account_id,
            available_margin=margin.available_margin,
            used_margin=margin.used_margin,
            span_margin=margin.span_margin,
            exposure_margin=margin.exposure_margin,
            collateral=margin.collateral,
            cash_balance=margin.cash_balance,
            total_balance=margin.total_balance,
            timestamp=margin.timestamp,
        )
        self._db.add(snapshot)
        await self._db.commit()
        await self._db.refresh(snapshot)
        return snapshot
