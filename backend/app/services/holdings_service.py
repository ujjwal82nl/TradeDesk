"""
HoldingsService: fetch, sync and merge holdings across broker accounts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import BrokerAccount
from app.models.holding import BrokerTradeHistory, Holding, HoldingLot
from app.schemas.holding import (
    BrokerHoldingBreakdown,
    HoldingLotsResponse,
    HoldingResponse,
    HoldingTradeLot,
    MergedHoldingResponse,
)
from app.services.broker_service import BrokerService

logger = logging.getLogger(__name__)

# In-memory TTL cache for broker trade histories: broker_account_id -> (timestamp, trades)
_TRADE_HISTORY_CACHE: Dict[int, Tuple[float, List[dict]]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


class HoldingsService:
    """Application-layer service for long-term equity holdings."""

    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self._db = db
        self._user_id = user_id
        self._broker_svc = BrokerService(db)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_all_holdings(
        self,
        broker_account_id: Optional[int] = None,
    ) -> List[HoldingResponse]:
        """
        Return all persisted holdings for the user.

        Args:
            broker_account_id: Filter to a single broker account when provided.
        """
        stmt = (
            select(Holding)
            .options(selectinload(Holding.broker_account).selectinload(BrokerAccount.broker))
            .join(BrokerAccount, Holding.broker_account_id == BrokerAccount.id)
            .where(BrokerAccount.user_id == self._user_id)
        )
        if broker_account_id is not None:
            stmt = stmt.where(Holding.broker_account_id == broker_account_id)

        result = await self._db.execute(stmt.order_by(Holding.symbol))
        holdings = result.scalars().all()
        
        responses: List[HoldingResponse] = []
        for h in holdings:
            bname = (
                h.broker_account.broker.display_name
                if h.broker_account and h.broker_account.broker
                else (h.broker_account.account_name if h.broker_account else None)
            )
            # Check broker capability: Dhan & Zerodha support historical trade lots
            supports_lots = bool(bname and ("dhan" in bname.lower() or "zerodha" in bname.lower()))
            resp = HoldingResponse.model_validate(h)
            resp.broker_name = bname
            resp.supports_trade_lots = supports_lots
            responses.append(resp)
        return responses

    async def get_merged_holdings(self) -> List[MergedHoldingResponse]:
        """
        Return a cross-broker merged view of all holdings.

        Holdings are grouped by symbol; a quantity-weighted average cost
        and totals are computed.
        """
        all_holdings = await self.get_all_holdings()
        merged: Dict[str, Dict] = {}

        for h in all_holdings:
            key = h.isin or h.symbol
            if key not in merged:
                merged[key] = {
                    "symbol": h.symbol,
                    "isin": h.isin,
                    "total_quantity": 0.0,
                    "total_cost": 0.0,  # quantity × avg_cost
                    "current_price": h.current_price,
                    "total_value": 0.0,
                    "total_pnl": 0.0,
                    "brokers": [],
                }
            entry = merged[key]
            entry["total_quantity"] += h.quantity
            entry["total_cost"] += h.quantity * h.average_cost
            entry["total_value"] += h.current_value
            entry["total_pnl"] += h.pnl
            entry["current_price"] = h.current_price  # latest wins
            entry["brokers"].append(
                BrokerHoldingBreakdown(
                    holding_id=h.id,
                    broker_name=h.broker_name or "Broker",
                    quantity=h.quantity,
                    average_cost=h.average_cost,
                    value=h.current_value,
                    pnl=h.pnl,
                    supports_trade_lots=h.supports_trade_lots,
                )
            )

        results: List[MergedHoldingResponse] = []
        for entry in merged.values():
            qty = entry["total_quantity"]
            weighted_avg = entry["total_cost"] / qty if qty else 0.0
            total_pnl_pct = (
                (entry["total_pnl"] / entry["total_cost"] * 100)
                if entry["total_cost"]
                else 0.0
            )
            results.append(
                MergedHoldingResponse(
                    symbol=entry["symbol"],
                    isin=entry["isin"],
                    total_quantity=qty,
                    weighted_avg_cost=weighted_avg,
                    current_price=entry["current_price"],
                    total_value=entry["total_value"],
                    total_pnl=entry["total_pnl"],
                    total_pnl_percent=total_pnl_pct,
                    brokers=entry["brokers"],
                )
            )
        return sorted(results, key=lambda r: r.symbol)

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync_holdings_from_broker(
        self,
        broker_account_id: int,
    ) -> List[Holding]:
        """
        Pull the latest holdings from the broker API and upsert into the DB.

        Existing DB rows for this account are overwritten; symbols no longer
        returned by the broker are soft-deleted (quantity set to 0).

        Returns:
            The refreshed list of Holding ORM objects.
        """
        adapter = await self._broker_svc.get_broker_instance(
            broker_account_id, self._user_id
        )
        raw_holdings: List[dict] = await adapter.get_holdings()

        # Load existing rows keyed by symbol for efficient upsert
        stmt = select(Holding).where(Holding.broker_account_id == broker_account_id)
        result = await self._db.execute(stmt)
        existing: Dict[str, Holding] = {h.symbol: h for h in result.scalars().all()}

        seen_symbols: set[str] = set()
        updated: List[Holding] = []

        for item in raw_holdings:
            raw = item.model_dump() if hasattr(item, "model_dump") else item
            symbol: str = raw["symbol"]
            seen_symbols.add(symbol)

            if symbol in existing:
                holding = existing[symbol]
            else:
                holding = Holding(
                    broker_account_id=broker_account_id,
                    symbol=symbol,
                )
                self._db.add(holding)

            holding.exchange = raw.get("exchange", "")
            holding.isin = raw.get("isin")
            holding.quantity = float(raw.get("quantity", 0))
            holding.average_cost = float(raw.get("average_cost") or raw.get("average_price") or 0)
            holding.current_price = float(raw.get("current_price") or raw.get("last_price") or 0)
            holding.current_value = float(raw.get("current_value") if raw.get("current_value") is not None else (holding.quantity * holding.current_price))
            holding.pnl = float(raw.get("pnl") if raw.get("pnl") is not None else (holding.current_value - holding.quantity * holding.average_cost))
            invested = holding.quantity * holding.average_cost
            if raw.get("pnl_percent") is not None:
                holding.pnl_percent = float(raw.get("pnl_percent"))
            elif invested != 0:
                holding.pnl_percent = round((holding.pnl / invested) * 100, 2)
            else:
                holding.pnl_percent = 0.0
            holding.day_change = float(raw.get("day_change", 0))
            holding.day_change_percent = float(
                raw.get("day_change_percent") or raw.get("day_change_percentage") or 0
            )
            holding.product_type = raw.get("product_type", "CNC")
            holding.instrument_type = raw.get("instrument_type", "EQ")
            holding.last_updated = datetime.utcnow()
            updated.append(holding)

        # Zero-out stale holdings no longer in the broker response
        for symbol, holding in existing.items():
            if symbol not in seen_symbols:
                holding.quantity = 0.0
                holding.current_value = 0.0
                holding.last_updated = datetime.utcnow()

        await self._db.commit()

        # If broker supports historical trade logs, synchronize trades and compute tax lots to DB
        if getattr(adapter, "supports_historical_trades", False):
            try:
                trades = await self.sync_broker_trade_history(broker_account_id)
                for h in updated:
                    if float(h.quantity or 0) > 0:
                        await self.calculate_and_save_holding_lots(h, trades)
            except Exception as exc:
                logger.warning("sync_holdings_from_broker: lot sync failed: %s", exc)

        return updated

    async def sync_holdings(self, broker_account_id: Optional[int] = None) -> List[Holding]:
        """Sync holdings from all (or specific) broker accounts."""
        accounts = await self._broker_svc.get_user_accounts(self._user_id)
        if broker_account_id is not None:
            accounts = [a for a in accounts if a.id == broker_account_id]
        all_holdings = []
        for acc in accounts:
            try:
                h = await self.sync_holdings_from_broker(acc.id)
                all_holdings.extend(h)
            except Exception as exc:
                logger.warning(
                    "sync_holdings: failed for broker account %s (%s): %s",
                    acc.id,
                    acc.account_name,
                    exc,
                )
        return all_holdings

    # ------------------------------------------------------------------
    # Trade Lots / Database Persistence & FIFO Construction
    # ------------------------------------------------------------------

    async def sync_broker_trade_history(
        self, broker_account_id: int
    ) -> List[BrokerTradeHistory]:
        """
        Fetch historical trades from broker and persist them permanently in broker_trade_history table.

        Subsequent calculations read directly from local PostgreSQL, eliminating API latency.
        """
        adapter = await self._broker_svc.get_broker_instance(broker_account_id, self._user_id)
        if not getattr(adapter, "supports_historical_trades", False):
            return []

        raw_trades = await adapter.get_historical_trades()
        if not raw_trades:
            stmt = select(BrokerTradeHistory).where(
                BrokerTradeHistory.broker_account_id == broker_account_id
            )
            return (await self._db.execute(stmt)).scalars().all()

        # Load existing trade records to avoid duplicates
        stmt = select(BrokerTradeHistory).where(
            BrokerTradeHistory.broker_account_id == broker_account_id
        )
        existing_rows = (await self._db.execute(stmt)).scalars().all()
        existing_keys = {
            (
                str(r.order_id),
                str(r.trade_id or ""),
                str(r.exchange_time or ""),
                float(r.traded_quantity or 0),
            )
            for r in existing_rows
        }

        new_records: List[BrokerTradeHistory] = []
        for t in raw_trades:
            order_id = str(t.get("orderId") or "")
            trade_id = str(t.get("exchangeTradeId") or t.get("tradeId") or order_id)
            exchange_time = str(t.get("exchangeTime") or t.get("createTime") or "")
            qty_float = float(t.get("tradedQuantity") or 0)
            qty = Decimal(str(t.get("tradedQuantity") or 0))
            price = Decimal(str(t.get("tradedPrice") or 0))

            key = (order_id, trade_id, exchange_time, qty_float)
            if key in existing_keys:
                continue

            rec = BrokerTradeHistory(
                broker_account_id=broker_account_id,
                order_id=order_id,
                trade_id=trade_id,
                symbol=str(t.get("tradingSymbol") or t.get("customSymbol") or "").strip(),
                custom_symbol=str(t.get("customSymbol") or "").strip(),
                isin=str(t.get("isin") or "").strip(),
                exchange_segment=str(t.get("exchangeSegment") or "NSE_EQ"),
                transaction_type=str(t.get("transactionType") or "BUY").upper(),
                product_type=str(t.get("productType") or "CNC"),
                traded_quantity=qty,
                traded_price=price,
                trade_value=qty * price,
                exchange_time=exchange_time,
            )
            self._db.add(rec)
            existing_keys.add(key)
            new_records.append(rec)

        if new_records:
            await self._db.commit()

        # Return full history from DB
        stmt = (
            select(BrokerTradeHistory)
            .where(BrokerTradeHistory.broker_account_id == broker_account_id)
            .order_by(BrokerTradeHistory.exchange_time.asc())
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def calculate_and_save_holding_lots(
        self, holding: Holding, all_trades: List[BrokerTradeHistory]
    ) -> List[HoldingLot]:
        """
        Run FIFO ledger matching and store resulting open buy lots in holding_lots table.
        """
        holding_sym_clean = holding.symbol.upper().replace(" ", "").replace("-", "")
        holding_isin_clean = (holding.isin or "").upper().strip()
        total_qty = float(holding.quantity or 0)
        avg_cost = float(holding.average_cost or 0)

        # Filter trades for this holding
        matched_trades: List[BrokerTradeHistory] = []
        for t in all_trades:
            seg = str(t.exchange_segment or "").upper()
            if any(deriv in seg for deriv in ["FO", "OPT", "FUT", "COMM"]):
                continue

            t_isin = str(t.isin or "").upper().strip()
            t_sym = str(t.symbol or t.custom_symbol or "").upper()
            t_sym_clean = t_sym.replace(" ", "").replace("-", "")

            is_match = False
            if holding_isin_clean and t_isin and holding_isin_clean == t_isin:
                is_match = True
            elif holding_sym_clean in t_sym_clean or t_sym_clean in holding_sym_clean:
                is_match = True

            if is_match:
                matched_trades.append(t)

        matched_trades.sort(key=lambda x: str(x.exchange_time or ""))

        # Deduplicate trades by execution signature
        deduped_trades: List[BrokerTradeHistory] = []
        seen_trade_keys = set()
        for t in matched_trades:
            t_key = (
                str(t.order_id),
                str(t.trade_id or ""),
                str(t.exchange_time or ""),
                float(t.traded_quantity or 0),
            )
            if t_key not in seen_trade_keys:
                seen_trade_keys.add(t_key)
                deduped_trades.append(t)

        # FIFO matching
        open_lots_raw: List[dict] = []
        for t in deduped_trades:
            ttype = str(t.transaction_type or "").upper()
            qty = float(t.traded_quantity or 0)
            price = float(t.traded_price or 0.0)
            trade_time = str(t.exchange_time or "")
            order_id = str(t.order_id or "")
            trade_id = str(t.trade_id or order_id)

            if ttype == "BUY":
                open_lots_raw.append(
                    {
                        "trade_id": trade_id,
                        "order_id": order_id,
                        "trade_date": trade_time,
                        "orig_qty": qty,
                        "rem_qty": qty,
                        "price": price,
                        "exchange": str(t.exchange_segment or "NSE").replace("_EQ", ""),
                    }
                )
            elif ttype == "SELL":
                sell_rem = qty
                while sell_rem > 0 and open_lots_raw:
                    oldest = open_lots_raw[0]
                    if oldest["rem_qty"] <= sell_rem:
                        sell_rem -= oldest["rem_qty"]
                        open_lots_raw.pop(0)
                    else:
                        oldest["rem_qty"] -= sell_rem
                        sell_rem = 0

        # Clear existing lots for this holding in DB
        await self._db.execute(
            delete(HoldingLot).where(HoldingLot.holding_id == holding.id)
        )

        saved_lots: List[HoldingLot] = []
        total_matched_qty = 0.0

        for lot in open_lots_raw:
            rem = lot["rem_qty"]
            if rem <= 0:
                continue
            total_matched_qty += rem

            hl = HoldingLot(
                holding_id=holding.id,
                broker_account_id=holding.broker_account_id,
                trade_id=lot["trade_id"],
                order_id=lot["order_id"],
                trade_date=lot["trade_date"],
                transaction_type="BUY",
                quantity=Decimal(str(rem)),
                original_quantity=Decimal(str(lot["orig_qty"])),
                price=Decimal(str(lot["price"])),
                amount=Decimal(str(round(rem * lot["price"], 4))),
                exchange=lot["exchange"],
                is_opening_lot=False,
            )
            self._db.add(hl)
            saved_lots.append(hl)

        unmatched = max(0.0, total_qty - total_matched_qty)
        if unmatched > 0.001:
            hl_open = HoldingLot(
                holding_id=holding.id,
                broker_account_id=holding.broker_account_id,
                trade_id="OPENING_LOT",
                order_id="PRE_API_HISTORY",
                trade_date="Opening Balance",
                transaction_type="BUY",
                quantity=Decimal(str(unmatched)),
                original_quantity=Decimal(str(unmatched)),
                price=Decimal(str(avg_cost)),
                amount=Decimal(str(round(unmatched * avg_cost, 4))),
                exchange=holding.exchange or "NSE",
                is_opening_lot=True,
                notes="Acquired prior to available broker trade history window",
            )
            self._db.add(hl_open)
            saved_lots.append(hl_open)

        await self._db.commit()
        return saved_lots

    async def get_holding_lots(
        self, holding_id: int, force_refresh: bool = False
    ) -> HoldingLotsResponse:
        """
        Return open buy trades (tax lots) for a holding.

        Reads directly from local PostgreSQL holding_lots table for instant zero-latency access.
        If no lots exist in DB yet (or force_refresh=True), pulls trade history from broker,
        computes FIFO lots, persists them to DB, and returns.
        """
        stmt = (
            select(Holding)
            .options(selectinload(Holding.broker_account).selectinload(BrokerAccount.broker))
            .where(Holding.id == holding_id)
        )
        result = await self._db.execute(stmt)
        holding = result.scalar_one_or_none()
        if not holding or holding.broker_account.user_id != self._user_id:
            raise ValueError(f"Holding with ID {holding_id} not found.")

        bname = (
            holding.broker_account.broker.display_name
            if holding.broker_account and holding.broker_account.broker
            else "Broker"
        )
        total_qty = float(holding.quantity or 0)
        avg_cost = float(holding.average_cost or 0)
        curr_price = float(holding.current_price or 0)
        curr_val = float(holding.current_value or (total_qty * curr_price))
        pnl = float(holding.pnl or (curr_val - total_qty * avg_cost))
        pnl_pct = float(
            holding.pnl_percent
            or (((curr_price - avg_cost) / avg_cost * 100) if avg_cost else 0)
        )

        adapter = await self._broker_svc.get_broker_instance(
            holding.broker_account_id, self._user_id
        )
        supports_hist = getattr(adapter, "supports_historical_trades", False)

        if not supports_hist:
            return HoldingLotsResponse(
                holding_id=holding.id,
                symbol=holding.symbol,
                isin=holding.isin,
                broker_name=bname,
                broker_account_id=holding.broker_account_id,
                total_quantity=total_qty,
                average_cost=avg_cost,
                current_price=curr_price,
                current_value=curr_val,
                total_pnl=pnl,
                total_pnl_percent=pnl_pct,
                supports_historical_trades=False,
                unmatched_quantity=total_qty,
                lots=[],
                message=f"Broker '{bname}' does not provide historical trade executions via API. Displaying standard holding summary.",
            )

        # 1. Check if lots already exist in local DB (Instant response, zero network delay)
        if not force_refresh:
            lot_stmt = (
                select(HoldingLot)
                .where(HoldingLot.holding_id == holding.id)
                .order_by(HoldingLot.id.desc())
            )
            db_lots = (await self._db.execute(lot_stmt)).scalars().all()
            if db_lots:
                lots: List[HoldingTradeLot] = []
                now = datetime.utcnow()
                for dl in db_lots:
                    rem = float(dl.quantity)
                    price = float(dl.price)
                    orig_qty = float(dl.original_quantity)
                    lot_amount = float(dl.amount)
                    lot_curr_val = rem * curr_price
                    lot_pnl = lot_curr_val - lot_amount
                    lot_pnl_pct = (
                        ((curr_price - price) / price * 100)
                        if price > 0
                        else 0.0
                    )
                    days = 0
                    if dl.trade_date and dl.trade_date != "Opening Balance":
                        try:
                            dt = datetime.fromisoformat(
                                str(dl.trade_date).replace("Z", "+00:00").split("+")[0]
                            )
                            days = max(0, (now - dt).days)
                        except Exception:
                            days = 0

                    lots.append(
                        HoldingTradeLot(
                            trade_id=dl.trade_id,
                            order_id=dl.order_id,
                            trade_date=dl.trade_date,
                            transaction_type=dl.transaction_type,
                            quantity=rem,
                            original_quantity=orig_qty,
                            price=price,
                            amount=round(lot_amount, 2),
                            current_price=curr_price,
                            current_value=round(lot_curr_val, 2),
                            pnl=round(lot_pnl, 2),
                            pnl_percent=round(lot_pnl_pct, 2),
                            holding_days=days,
                            exchange=dl.exchange,
                            is_opening_lot=dl.is_opening_lot,
                            notes=dl.notes,
                        )
                    )

                matched_qty = sum(l.quantity for l in lots if not l.is_opening_lot)
                unmatched = max(0.0, total_qty - matched_qty)
                return HoldingLotsResponse(
                    holding_id=holding.id,
                    symbol=holding.symbol,
                    isin=holding.isin,
                    broker_name=bname,
                    broker_account_id=holding.broker_account_id,
                    total_quantity=total_qty,
                    average_cost=avg_cost,
                    current_price=curr_price,
                    current_value=curr_val,
                    total_pnl=pnl,
                    total_pnl_percent=pnl_pct,
                    supports_historical_trades=True,
                    unmatched_quantity=unmatched,
                    lots=lots,
                )

        # 2. No lots in DB yet (or force_refresh requested): pull from broker, persist, and calculate
        try:
            trades = await self.sync_broker_trade_history(holding.broker_account_id)
            await self.calculate_and_save_holding_lots(holding, trades)
        except Exception as exc:
            logger.warning("Failed to sync historical trades to DB: %s", exc)
            return HoldingLotsResponse(
                holding_id=holding.id,
                symbol=holding.symbol,
                isin=holding.isin,
                broker_name=bname,
                broker_account_id=holding.broker_account_id,
                total_quantity=total_qty,
                average_cost=avg_cost,
                current_price=curr_price,
                current_value=curr_val,
                total_pnl=pnl,
                total_pnl_percent=pnl_pct,
                supports_historical_trades=True,
                unmatched_quantity=total_qty,
                lots=[],
                message=f"Failed to fetch historical trades from {bname}: {exc}",
            )

        # Re-query saved lots from DB
        return await self.get_holding_lots(holding_id, force_refresh=False)

    async def get_lots_by_symbol(
        self, symbol: str, force_refresh: bool = False
    ) -> List[HoldingLotsResponse]:
        """Return trade lots breakdown for all holdings matching a given symbol."""
        stmt = (
            select(Holding)
            .options(selectinload(Holding.broker_account).selectinload(BrokerAccount.broker))
            .join(BrokerAccount, Holding.broker_account_id == BrokerAccount.id)
            .where(BrokerAccount.user_id == self._user_id)
            .where(Holding.symbol == symbol.upper())
        )
        result = await self._db.execute(stmt)
        holdings = result.scalars().all()
        responses: List[HoldingLotsResponse] = []
        for h in holdings:
            resp = await self.get_holding_lots(h.id, force_refresh=force_refresh)
            responses.append(resp)
        return responses
