"""
Algo Strategy Service.
Manages automated algorithmic strategy execution, including 0DTE Crypto Options Selling (Theta Gainers).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta, time as dtime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import httpx
import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.algo import AlgoRun, AlgoStatus, AlgoMode, AlgoStrategy, TradeSignal, SignalType
from app.models.user import User
from app.services.telegram_service import TelegramService

log = structlog.get_logger()

# Indian Standard Time offset (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class AlgoService:
    """Service to evaluate and execute algorithmic trading strategies."""

    DELTA_API_BASE = "https://api.delta.exchange/v2"

    @classmethod
    async def fetch_btc_0dte_options(cls, target_premium: float = 100.0) -> Dict[str, Any]:
        """
        Fetch active 0DTE (same day expiry) BTC options contracts from Delta Exchange
        and find the Call and Put strikes whose LTP/mark price is closest to target_premium.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Fetch live products
            prod_resp = await client.get(f"{cls.DELTA_API_BASE}/products")
            if prod_resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch Delta products: HTTP {prod_resp.status_code}")

            products_raw = prod_resp.json().get("result", [])

            # Filter for BTC options
            btc_options = [
                p for p in products_raw
                if p.get("underlying_asset", {}).get("symbol") == "BTC"
                and p.get("contract_type") in ("call_options", "put_options")
                and p.get("trading_status") == "operational"
            ]

            if not btc_options:
                raise RuntimeError("No active operational BTC options found.")

            # Find distinct settlement times (expiries)
            expiries = sorted(list(set(p.get("settlement_time") for p in btc_options if p.get("settlement_time"))))
            if not expiries:
                raise RuntimeError("No settlement times found for BTC options.")

            # The earliest upcoming expiry is 0DTE
            # e.g., '2026-11-28T12:00:00Z' (12:00 UTC = 17:30 IST)
            now_utc = datetime.now(timezone.utc)
            future_expiries = []
            for exp_str in expiries:
                try:
                    exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                    if exp_dt > now_utc:
                        future_expiries.append((exp_dt, exp_str))
                except Exception:
                    pass

            if not future_expiries:
                # Fallback to first available expiry
                target_expiry_str = expiries[0]
                target_expiry_dt = datetime.fromisoformat(target_expiry_str.replace("Z", "+00:00"))
            else:
                target_expiry_dt, target_expiry_str = future_expiries[0]

            expiry_products = {
                p["symbol"]: p for p in btc_options
                if p.get("settlement_time") == target_expiry_str
            }

            # 2. Fetch live tickers for mark prices
            tick_resp = await client.get(f"{cls.DELTA_API_BASE}/tickers")
            if tick_resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch Delta tickers: HTTP {tick_resp.status_code}")

            tickers_raw = tick_resp.json().get("result", [])
            tickers_map = {
                t["symbol"]: float(t.get("mark_price") or t.get("close") or 0.0)
                for t in tickers_raw if t.get("symbol") in expiry_products
            }

            # Group into calls and puts
            calls = []
            puts = []
            for sym, prod in expiry_products.items():
                mark = tickers_map.get(sym, 0.0)
                if mark <= 0.0:
                    continue
                strike = float(prod.get("strike_price") or 0.0)
                c_type = prod.get("contract_type")
                entry = {
                    "symbol": sym,
                    "strike": strike,
                    "mark_price": mark,
                    "diff": abs(mark - target_premium),
                    "contract_type": "CE" if c_type == "call_options" else "PE",
                    "expiry": target_expiry_str,
                }
                if c_type == "call_options":
                    calls.append(entry)
                elif c_type == "put_options":
                    puts.append(entry)

            if not calls or not puts:
                raise RuntimeError(f"Could not find matching Call or Put options for expiry {target_expiry_str}")

            calls.sort(key=lambda x: x["diff"])
            puts.sort(key=lambda x: x["diff"])

            best_call = calls[0]
            best_put = puts[0]

            return {
                "expiry_str": target_expiry_str,
                "expiry_ist": target_expiry_dt.astimezone(IST).strftime("%d-%b-%Y %H:%M IST"),
                "target_premium": target_premium,
                "best_call": best_call,
                "best_put": best_put,
                "top_calls": calls[:3],
                "top_puts": puts[:3],
            }

    @classmethod
    async def evaluate_btc_0dte_strategy(
        cls,
        strategy: AlgoStrategy,
        session: AsyncSession,
        force_simulate: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates the 0DTE BTC Options Selling strategy:
        1. Checks time: Entry at 09:00 IST, Exit at 16:00 IST.
        2. Sells Call and Put with premium closest to 100.
        3. Enforces 100% stop loss on each leg independently.
        4. Squares off remaining legs at 16:00 IST.
        """
        now_ist = datetime.now(IST)
        today_str = now_ist.strftime("%Y-%m-%d")

        entry_params = strategy.entry_params or {}
        exit_params = strategy.exit_params or {}

        target_premium = float(entry_params.get("target_premium", 100.0))
        sl_pct = float(exit_params.get("sl_value", 100.0))  # 100% stop loss
        entry_time_str = entry_params.get("entry_time", "09:00:00")
        squareoff_time_str = exit_params.get("squareoff_time", "16:00:00")

        # Parse times
        h_entry, m_entry = map(int, entry_time_str.split(":")[:2])
        h_exit, m_exit = map(int, squareoff_time_str.split(":")[:2])
        entry_t = dtime(h_entry, m_entry)
        exit_t = dtime(h_exit, m_exit)
        current_t = now_ist.time()

        # Check for existing run for today
        run_name_prefix = f"{strategy.name} - {today_str}"
        query = select(AlgoRun).where(
            and_(
                AlgoRun.user_id == strategy.user_id,
                AlgoRun.name.like(f"{strategy.name}%{today_str}%")
            )
        ).order_by(AlgoRun.id.desc())
        res = await session.execute(query)
        active_run = res.scalars().first()

        # -------------------------------------------------------------
        # 1. State: No Run Yet (Waiting or Entry Window)
        # -------------------------------------------------------------
        if not active_run or (force_simulate and active_run.status == AlgoStatus.STOPPED):
            # Check if it's entry time (or force_simulate)
            is_entry_time = (current_t >= entry_t and current_t < exit_t) or force_simulate

            if not is_entry_time and not force_simulate:
                return {
                    "strategy_id": strategy.id,
                    "strategy_name": strategy.name,
                    "status": "WAITING_FOR_ENTRY_TIME",
                    "current_ist": now_ist.strftime("%H:%M:%S"),
                    "entry_time": entry_time_str,
                    "message": f"Waiting for entry time ({entry_time_str} IST). Current time is {now_ist.strftime('%H:%M:%S')} IST.",
                }

            # Fetch live 0DTE options
            options_data = await cls.fetch_btc_0dte_options(target_premium=target_premium)
            call_leg = options_data["best_call"]
            put_leg = options_data["best_put"]

            call_entry = call_leg["mark_price"]
            put_entry = put_leg["mark_price"]
            call_sl = call_entry * (1.0 + sl_pct / 100.0)  # e.g., 100 * 2.0 = 200
            put_sl = put_entry * (1.0 + sl_pct / 100.0)

            run_config = {
                "date": today_str,
                "strategy_id": strategy.id,
                "target_premium": target_premium,
                "sl_pct": sl_pct,
                "call_leg": {
                    "symbol": call_leg["symbol"],
                    "strike": call_leg["strike"],
                    "entry_price": call_entry,
                    "sl_price": call_sl,
                    "current_price": call_entry,
                    "lots": 1,
                    "status": "OPEN",
                    "entered_at": now_ist.isoformat(),
                    "pnl": 0.0,
                },
                "put_leg": {
                    "symbol": put_leg["symbol"],
                    "strike": put_leg["strike"],
                    "entry_price": put_entry,
                    "sl_price": put_sl,
                    "current_price": put_entry,
                    "lots": 1,
                    "status": "OPEN",
                    "entered_at": now_ist.isoformat(),
                    "pnl": 0.0,
                },
                "total_pnl": 0.0,
                "expiry_ist": options_data["expiry_ist"],
            }

            new_run = AlgoRun(
                user_id=strategy.user_id,
                name=f"{strategy.name} - {today_str}",
                strategy_code="0DTE_BTC_SELLING",
                mode=AlgoMode(strategy.mode if strategy.mode in ("PAPER", "LIVE") else "PAPER"),
                status=AlgoStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                config=run_config,
            )
            session.add(new_run)
            await session.flush()

            # Record Trade Signals
            sig_call = TradeSignal(
                algo_run_id=new_run.id,
                symbol=call_leg["symbol"],
                exchange="COINDCX",
                signal_type=SignalType.SELL,
                price=Decimal(str(round(call_entry, 2))),
                quantity=1,
                strategy_name=strategy.name,
                executed=True,
                executed_at=datetime.now(timezone.utc),
                notes=f"Sold 0DTE Call @ ${call_entry:.2f} (SL: ${call_sl:.2f} | +{sl_pct:.0f}%)",
            )
            sig_put = TradeSignal(
                algo_run_id=new_run.id,
                symbol=put_leg["symbol"],
                exchange="COINDCX",
                signal_type=SignalType.SELL,
                price=Decimal(str(round(put_entry, 2))),
                quantity=1,
                strategy_name=strategy.name,
                executed=True,
                executed_at=datetime.now(timezone.utc),
                notes=f"Sold 0DTE Put @ ${put_entry:.2f} (SL: ${put_sl:.2f} | +{sl_pct:.0f}%)",
            )
            session.add_all([sig_call, sig_put])

            strategy.last_run_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(new_run)

            # Send Telegram alert
            tg_msg = (
                f"🚀 <b>0DTE_BTC_Selling — Short Strangle Executed!</b>\n\n"
                f"🤖 <b>Strategy:</b> {strategy.name} ({strategy.mode} Mode)\n"
                f"⏰ <b>Entry Time:</b> {now_ist.strftime('%H:%M:%S')} IST\n"
                f"📅 <b>Expiry:</b> {options_data['expiry_ist']} (0DTE)\n\n"
                f"🔴 <b>Leg 1 (CALL):</b> Sold <code>{call_leg['symbol']}</code>\n"
                f"   • Strike: <b>${call_leg['strike']:,.0f}</b>\n"
                f"   • Entry Price: <b>${call_entry:.2f}</b>\n"
                f"   • Stop Loss (100%): <b>${call_sl:.2f}</b>\n\n"
                f"🔴 <b>Leg 2 (PUT):</b> Sold <code>{put_leg['symbol']}</code>\n"
                f"   • Strike: <b>${put_leg['strike']:,.0f}</b>\n"
                f"   • Entry Price: <b>${put_entry:.2f}</b>\n"
                f"   • Stop Loss (100%): <b>${put_sl:.2f}</b>\n\n"
                f"🎯 <b>Square-Off Target:</b> {squareoff_time_str} IST\n"
                f"⚡ <i>TradeDesk Automated 0DTE Crypto Engine</i>"
            )
            await TelegramService.send_message(tg_msg)

            return {
                "strategy_id": strategy.id,
                "strategy_name": strategy.name,
                "status": "ENTERED_POSITIONS",
                "run_id": new_run.id,
                "call_leg": run_config["call_leg"],
                "put_leg": run_config["put_leg"],
                "message": f"Positions executed: Sold Call {call_leg['symbol']} @ ${call_entry:.2f} and Put {put_leg['symbol']} @ ${put_entry:.2f}",
            }

        # -------------------------------------------------------------
        # 2. State: Active Run — Monitor Live Prices, SL & Square-off
        # -------------------------------------------------------------
        if active_run.status == AlgoStatus.RUNNING:
            config = dict(active_run.config or {})
            call_leg = config.get("call_leg", {})
            put_leg = config.get("put_leg", {})

            # Fetch live tickers
            symbols_to_query = [call_leg.get("symbol"), put_leg.get("symbol")]
            symbols_to_query = [s for s in symbols_to_query if s]

            live_prices = {}
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    t_resp = await client.get(f"{cls.DELTA_API_BASE}/tickers")
                    if t_resp.status_code == 200:
                        t_data = t_resp.json().get("result", [])
                        for item in t_data:
                            if item.get("symbol") in symbols_to_query:
                                live_prices[item["symbol"]] = float(item.get("mark_price") or item.get("close") or 0.0)
            except Exception as exc:
                log.warning("failed_to_fetch_live_tickers_for_algo", error=str(exc))

            call_sym = call_leg.get("symbol")
            put_sym = put_leg.get("symbol")
            cur_call_price = live_prices.get(call_sym, call_leg.get("current_price", call_leg.get("entry_price", 0.0)))
            cur_put_price = live_prices.get(put_sym, put_leg.get("current_price", put_leg.get("entry_price", 0.0)))

            call_leg["current_price"] = cur_call_price
            put_leg["current_price"] = cur_put_price

            # Update unrealized / realized PnL
            if call_leg.get("status") == "OPEN":
                call_leg["pnl"] = round((call_leg["entry_price"] - cur_call_price) * call_leg.get("lots", 1), 2)
            if put_leg.get("status") == "OPEN":
                put_leg["pnl"] = round((put_leg["entry_price"] - cur_put_price) * put_leg.get("lots", 1), 2)

            events_triggered = []

            # Check Stop Loss on Call Leg (100% SL)
            if call_leg.get("status") == "OPEN" and cur_call_price >= call_leg.get("sl_price", 999999):
                call_leg["status"] = "SL_HIT"
                call_leg["exit_price"] = cur_call_price
                call_leg["exited_at"] = now_ist.isoformat()
                loss = round((call_leg["entry_price"] - cur_call_price) * call_leg.get("lots", 1), 2)
                call_leg["pnl"] = loss
                events_triggered.append(f"Call SL Hit at ${cur_call_price:.2f} (Loss: ${loss:.2f})")

                # Log Exit Signal
                session.add(TradeSignal(
                    algo_run_id=active_run.id,
                    symbol=call_sym,
                    exchange="COINDCX",
                    signal_type=SignalType.BUY,
                    price=Decimal(str(round(cur_call_price, 2))),
                    quantity=int(call_leg.get("lots", 1)),
                    strategy_name=strategy.name,
                    executed=True,
                    executed_at=datetime.now(timezone.utc),
                    notes=f"Call Stop Loss Hit @ ${cur_call_price:.2f} (100% SL trigger)",
                ))

                tg_alert = (
                    f"⚠️ <b>0DTE_BTC_Selling — Stop Loss Hit on Call Leg!</b>\n\n"
                    f"🔴 <b>Leg:</b> CALL <code>{call_sym}</code>\n"
                    f"• Entry: ${call_leg['entry_price']:.2f} ➔ Exit: <b>${cur_call_price:.2f}</b>\n"
                    f"• Loss: <b>${loss:.2f}</b> (-100% SL Triggered)\n"
                    f"🛡️ Put Leg remains active: <code>{put_sym}</code> (LTP: ${cur_put_price:.2f})"
                )
                await TelegramService.send_message(tg_alert)

            # Check Stop Loss on Put Leg (100% SL)
            if put_leg.get("status") == "OPEN" and cur_put_price >= put_leg.get("sl_price", 999999):
                put_leg["status"] = "SL_HIT"
                put_leg["exit_price"] = cur_put_price
                put_leg["exited_at"] = now_ist.isoformat()
                loss = round((put_leg["entry_price"] - cur_put_price) * put_leg.get("lots", 1), 2)
                put_leg["pnl"] = loss
                events_triggered.append(f"Put SL Hit at ${cur_put_price:.2f} (Loss: ${loss:.2f})")

                # Log Exit Signal
                session.add(TradeSignal(
                    algo_run_id=active_run.id,
                    symbol=put_sym,
                    exchange="COINDCX",
                    signal_type=SignalType.BUY,
                    price=Decimal(str(round(cur_put_price, 2))),
                    quantity=int(put_leg.get("lots", 1)),
                    strategy_name=strategy.name,
                    executed=True,
                    executed_at=datetime.now(timezone.utc),
                    notes=f"Put Stop Loss Hit @ ${cur_put_price:.2f} (100% SL trigger)",
                ))

                tg_alert = (
                    f"⚠️ <b>0DTE_BTC_Selling — Stop Loss Hit on Put Leg!</b>\n\n"
                    f"🔴 <b>Leg:</b> PUT <code>{put_sym}</code>\n"
                    f"• Entry: ${put_leg['entry_price']:.2f} ➔ Exit: <b>${cur_put_price:.2f}</b>\n"
                    f"• Loss: <b>${loss:.2f}</b> (-100% SL Triggered)\n"
                    f"🛡️ Call Leg status: {call_leg.get('status')} (LTP: ${cur_call_price:.2f})"
                )
                await TelegramService.send_message(tg_alert)

            # Check 16:00 IST Square-Off Time
            is_squareoff_time = current_t >= exit_t
            if is_squareoff_time:
                # Square off any open legs
                if call_leg.get("status") == "OPEN":
                    call_leg["status"] = "SQUARED_OFF"
                    call_leg["exit_price"] = cur_call_price
                    call_leg["exited_at"] = now_ist.isoformat()
                    call_leg["pnl"] = round((call_leg["entry_price"] - cur_call_price) * call_leg.get("lots", 1), 2)

                if put_leg.get("status") == "OPEN":
                    put_leg["status"] = "SQUARED_OFF"
                    put_leg["exit_price"] = cur_put_price
                    put_leg["exited_at"] = now_ist.isoformat()
                    put_leg["pnl"] = round((put_leg["entry_price"] - cur_put_price) * put_leg.get("lots", 1), 2)

                active_run.status = AlgoStatus.STOPPED
                active_run.stopped_at = datetime.now(timezone.utc)
                events_triggered.append("Square-off time 16:00 IST reached. Strategy completed.")

            total_pnl = round(call_leg.get("pnl", 0.0) + put_leg.get("pnl", 0.0), 2)
            config["total_pnl"] = total_pnl
            config["call_leg"] = call_leg
            config["put_leg"] = put_leg
            active_run.config = config

            await session.commit()

            if is_squareoff_time:
                tg_summary = (
                    f"🏁 <b>0DTE_BTC_Selling — Daily Square-Off Completed!</b>\n\n"
                    f"⏰ <b>Square-Off Time:</b> {now_ist.strftime('%H:%M:%S')} IST\n"
                    f"💰 <b>Total Strategy PnL:</b> <b>{'+' if total_pnl >= 0 else ''}${total_pnl:,.2f}</b>\n"
                    f"• Call Leg: {call_leg.get('status')} (PnL: ${call_leg.get('pnl', 0.0):+.2f})\n"
                    f"• Put Leg: {put_leg.get('status')} (PnL: ${put_leg.get('pnl', 0.0):+.2f})\n\n"
                    f"🎉 <i>Theta decay successfully harvested for today!</i>"
                )
                await TelegramService.send_message(tg_summary)

            return {
                "strategy_id": strategy.id,
                "strategy_name": strategy.name,
                "status": active_run.status.value,
                "run_id": active_run.id,
                "call_leg": call_leg,
                "put_leg": put_leg,
                "total_pnl": total_pnl,
                "events": events_triggered,
                "message": f"Monitoring active. Total PnL: ${total_pnl:+.2f}. Events: {', '.join(events_triggered) if events_triggered else 'No triggers'}",
            }

        return {
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "status": active_run.status.value,
            "message": f"Strategy run for {today_str} is currently {active_run.status.value}.",
        }

    @classmethod
    async def evaluate_all_active_strategies(cls, session: AsyncSession) -> None:
        """Background evaluator called every minute by the background worker."""
        # Find all active strategies
        query = select(AlgoStrategy).where(AlgoStrategy.is_active.is_(True))
        res = await session.execute(query)
        strategies = res.scalars().all()

        for strat in strategies:
            try:
                if "BTC" in strat.underlying.upper() or "0DTE" in strat.name.upper() or strat.template_type == "0DTE_BTC_SELLING":
                    await cls.evaluate_btc_0dte_strategy(strat, session)
            except Exception as exc:
                log.warning("algo_strategy_eval_error", strategy=strat.name, error=str(exc))
