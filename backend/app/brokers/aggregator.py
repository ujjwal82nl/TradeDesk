"""
aggregator.py – PortfolioAggregator: merges data from multiple broker adapters.

Usage::

    from app.brokers.aggregator import PortfolioAggregator
    from app.brokers.adapters import DhanAdapter, ZerodhaAdapter

    brokers = [
        ("dhan", DhanAdapter(client_id=..., access_token=...)),
        ("zerodha", ZerodhaAdapter(api_key=..., access_token=...)),
    ]
    agg = PortfolioAggregator(brokers)
    summary = await agg.get_portfolio_summary()
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.brokers.base import BaseBroker, FundsData, HoldingData, PositionData

logger = logging.getLogger(__name__)

# Type alias for a labelled broker pair
BrokerEntry = Tuple[str, BaseBroker]


class PortfolioAggregator:
    """Aggregates portfolio data across multiple broker adapters.

    All ``get_aggregated_*`` methods run each broker's network call
    concurrently using ``asyncio.gather``.  Individual broker failures
    are caught and logged so one failing broker never blocks the rest.

    Args:
        brokers: List of ``(broker_name, adapter_instance)`` tuples.

    Example::

        agg = PortfolioAggregator([
            ("dhan", dhan_adapter),
            ("zerodha", zerodha_adapter),
        ])
        holdings = await agg.get_aggregated_holdings()
    """

    def __init__(self, brokers: List[BrokerEntry]) -> None:
        if not brokers:
            raise ValueError("PortfolioAggregator requires at least one broker.")
        self._brokers = brokers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _gather_broker_results(self, method_name: str) -> Dict[str, Any]:
        """Call *method_name* on every broker concurrently.

        Returns:
            Dict mapping broker_name → result (or ``None`` on error).
        """
        async def _fetch(name: str, broker: BaseBroker):
            try:
                result = await getattr(broker, method_name)()
                return name, result
            except NotImplementedError:
                logger.info(
                    "aggregator.%s: broker '%s' not implemented – skipping",
                    method_name, name,
                )
                return name, None
            except Exception as exc:
                logger.error(
                    "aggregator.%s: broker '%s' failed – %s",
                    method_name, name, exc, exc_info=True,
                )
                return name, None

        tasks = [_fetch(name, broker) for name, broker in self._brokers]
        pairs = await asyncio.gather(*tasks)
        return {name: result for name, result in pairs}

    # ------------------------------------------------------------------
    # Holdings aggregation
    # ------------------------------------------------------------------

    async def get_aggregated_holdings(self) -> Dict[str, Any]:
        """Merge holdings by ISIN (falling back to symbol) across all brokers.

        Returns a dict with:
        - ``by_broker``: per-broker raw list of holdings
        - ``by_isin``: merged holdings keyed by ISIN showing combined
          quantity, weighted average cost, total value, total P&L and a
          breakdown per broker
        - ``total_value``: combined current market value across all brokers
        - ``total_pnl``: combined unrealised P&L across all brokers
        - ``total_pnl_percent``: portfolio-level P&L percentage
        """
        broker_results = await self._gather_broker_results("get_holdings")

        by_broker: Dict[str, List[Dict]] = {}
        # isin (or symbol) → aggregated record
        merged: Dict[str, Dict[str, Any]] = {}

        for broker_name, holdings in broker_results.items():
            if holdings is None:
                by_broker[broker_name] = []
                continue

            serialised = [h.model_dump() for h in holdings]
            by_broker[broker_name] = serialised

            for holding in holdings:
                key = holding.isin if holding.isin else f"SYM:{holding.symbol}"

                if key not in merged:
                    merged[key] = {
                        "isin": holding.isin,
                        "symbol": holding.symbol,
                        "instrument_type": holding.instrument_type,
                        "total_quantity": 0,
                        "total_cost_basis": 0.0,  # sum(avg_cost * qty) per broker
                        "total_value": 0.0,
                        "total_pnl": 0.0,
                        "current_price": holding.current_price,
                        "day_change": holding.day_change,
                        "day_change_percent": holding.day_change_percent,
                        "breakdown": [],
                    }

                rec = merged[key]
                rec["total_quantity"] += holding.quantity
                rec["total_cost_basis"] += holding.average_cost * holding.quantity
                rec["total_value"] += holding.current_value
                rec["total_pnl"] += holding.pnl
                # Use the latest price we saw (last broker wins)
                rec["current_price"] = holding.current_price
                rec["day_change"] = holding.day_change
                rec["day_change_percent"] = holding.day_change_percent
                rec["breakdown"].append(
                    {
                        "broker": broker_name,
                        "quantity": holding.quantity,
                        "average_cost": holding.average_cost,
                        "current_value": holding.current_value,
                        "pnl": holding.pnl,
                        "pnl_percent": holding.pnl_percent,
                        "product_type": holding.product_type,
                        "exchange": holding.exchange,
                    }
                )

        # Compute weighted average cost and P&L % for each merged record
        for rec in merged.values():
            qty = rec["total_quantity"]
            cost_basis = rec["total_cost_basis"]
            if qty and cost_basis:
                rec["weighted_average_cost"] = cost_basis / qty
                rec["total_pnl_percent"] = round(
                    (rec["total_pnl"] / cost_basis) * 100, 2
                )
            else:
                rec["weighted_average_cost"] = 0.0
                rec["total_pnl_percent"] = 0.0

        total_value = sum(r["total_value"] for r in merged.values())
        total_pnl = sum(r["total_pnl"] for r in merged.values())
        total_cost = sum(r["total_cost_basis"] for r in merged.values())
        total_pnl_pct = round((total_pnl / total_cost) * 100, 2) if total_cost else 0.0

        return {
            "by_broker": by_broker,
            "by_isin": merged,
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percent": total_pnl_pct,
        }

    # ------------------------------------------------------------------
    # Positions aggregation
    # ------------------------------------------------------------------

    async def get_aggregated_positions(self) -> Dict[str, Any]:
        """Merge all open positions from every broker.

        Returns a dict with:
        - ``by_broker``: per-broker position lists
        - ``all_positions``: flat list of all positions tagged with broker
        - ``total_pnl``: combined unrealised P&L
        - ``total_day_pnl``: combined realised / day P&L
        """
        broker_results = await self._gather_broker_results("get_positions")

        by_broker: Dict[str, List[Dict]] = {}
        all_positions: List[Dict[str, Any]] = []
        total_pnl = 0.0
        total_day_pnl = 0.0

        for broker_name, positions in broker_results.items():
            if positions is None:
                by_broker[broker_name] = []
                continue

            serialised = []
            for pos in positions:
                row = pos.model_dump()
                row["broker"] = broker_name
                serialised.append(row)
                total_pnl += pos.pnl
                total_day_pnl += pos.day_pnl

            by_broker[broker_name] = serialised
            all_positions.extend(serialised)

        return {
            "by_broker": by_broker,
            "all_positions": all_positions,
            "total_pnl": round(total_pnl, 2),
            "total_day_pnl": round(total_day_pnl, 2),
        }

    # ------------------------------------------------------------------
    # Funds aggregation
    # ------------------------------------------------------------------

    async def get_aggregated_funds(self) -> Dict[str, Any]:
        """Sum fund / margin data across all brokers.

        Returns a dict with:
        - ``by_broker``: per-broker :class:`FundsData` serialised as dict
        - ``combined``: summed totals across all active brokers
        """
        broker_results = await self._gather_broker_results("get_funds")

        by_broker: Dict[str, Optional[Dict]] = {}
        combined = {
            "available_margin": 0.0,
            "used_margin": 0.0,
            "span_margin": 0.0,
            "exposure_margin": 0.0,
            "collateral": 0.0,
            "cash_balance": 0.0,
            "total_balance": 0.0,
        }

        for broker_name, funds in broker_results.items():
            if funds is None:
                by_broker[broker_name] = None
                continue

            serialised = funds.model_dump()
            by_broker[broker_name] = serialised

            for field in combined:
                combined[field] += getattr(funds, field, 0.0)

        combined = {k: round(v, 2) for k, v in combined.items()}

        return {
            "by_broker": by_broker,
            "combined": combined,
        }

    # ------------------------------------------------------------------
    # Portfolio summary
    # ------------------------------------------------------------------

    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """Return a high-level portfolio snapshot across all brokers.

        Fetches holdings, positions, and funds concurrently and derives:
        - ``total_net_worth``:  holdings value + open positions value + cash
        - ``today_pnl``:        day P&L from holdings + positions
        - ``unrealized_pnl``:   P&L on open positions
        - ``realized_pnl``:     day realised P&L from positions

        Returns a flat dict suitable for a dashboard overview widget.
        """
        holdings_task = asyncio.create_task(self.get_aggregated_holdings())
        positions_task = asyncio.create_task(self.get_aggregated_positions())
        funds_task = asyncio.create_task(self.get_aggregated_funds())

        holdings_agg, positions_agg, funds_agg = await asyncio.gather(
            holdings_task, positions_task, funds_task
        )

        holdings_value: float = holdings_agg.get("total_value", 0.0)
        holdings_pnl: float = holdings_agg.get("total_pnl", 0.0)

        # Day change from all holdings
        holdings_day_pnl: float = sum(
            sum(b.get("day_change", 0.0) * b.get("quantity", 0) for b in rec.get("breakdown", []))
            for rec in holdings_agg.get("by_isin", {}).values()
        )

        positions_pnl: float = positions_agg.get("total_pnl", 0.0)
        positions_day_pnl: float = positions_agg.get("total_day_pnl", 0.0)
        cash: float = funds_agg.get("combined", {}).get("cash_balance", 0.0)
        collateral: float = funds_agg.get("combined", {}).get("collateral", 0.0)

        total_net_worth = holdings_value + cash + collateral
        today_pnl = holdings_day_pnl + positions_day_pnl

        # Count active brokers (those that returned data)
        active_brokers = [
            name for name, data in funds_agg.get("by_broker", {}).items()
            if data is not None
        ]

        return {
            "total_net_worth": round(total_net_worth, 2),
            "holdings_value": round(holdings_value, 2),
            "cash_balance": round(cash, 2),
            "collateral": round(collateral, 2),
            "today_pnl": round(today_pnl, 2),
            "unrealized_pnl": round(positions_pnl, 2),
            "realized_pnl": round(positions_day_pnl, 2),
            "total_holdings_pnl": round(holdings_pnl, 2),
            "active_brokers": active_brokers,
            "broker_count": len(active_brokers),
        }
