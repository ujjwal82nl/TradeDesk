"""
Alert Service for evaluating technical indicators (SuperTrend) and dispatching alerts.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertNotification, AlertRule, SignalState
from app.services.telegram_service import TelegramService

log = structlog.get_logger()


class AlertService:
    """Evaluates technical indicators and manages alert triggers."""

    @classmethod
    async def fetch_candles(
        cls,
        symbol: str = "BTCUSD",
        timeframe_minutes: int = 90,
        limit_candles: int = 150,
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candlestick data.
        For 90m timeframe: fetches 30m candles from Binance / CoinDCX and resamples 3x 30m -> 90m.
        """
        # Normalize symbol for Binance / CoinDCX
        sym_clean = symbol.upper().replace("-", "").replace("_", "")
        if sym_clean in ("BTCUSD", "BTCUSDT"):
            binance_sym = "BTCUSDT"
        else:
            binance_sym = sym_clean

        # Determine base interval and chunk size
        if timeframe_minutes % 30 == 0:
            base_interval = "30m"
            chunk_size = timeframe_minutes // 30
        elif timeframe_minutes % 15 == 0:
            base_interval = "15m"
            chunk_size = timeframe_minutes // 15
        elif timeframe_minutes % 5 == 0:
            base_interval = "5m"
            chunk_size = timeframe_minutes // 5
        else:
            base_interval = "1m"
            chunk_size = timeframe_minutes

        fetch_limit = min(1000, max(100, limit_candles * chunk_size + 10))

        raw_candles: List[List[Any]] = []

        # 1. Try Binance public API
        binance_url = f"https://api.binance.com/api/v3/klines?symbol={binance_sym}&interval={base_interval}&limit={fetch_limit}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(binance_url)
                if res.status_code == 200:
                    raw_candles = res.json()
        except Exception as exc:
            log.warning("binance_fetch_candles_error", error=str(exc))

        # 2. Fallback to CoinDCX public API if Binance fails or empty
        if not raw_candles:
            coindcx_pair = "B-BTC_USDT" if "BTC" in sym_clean else f"B-{sym_clean}"
            coindcx_url = f"https://public.coindcx.com/market_data/candles?pair={coindcx_pair}&interval=1h"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get(coindcx_url)
                    if res.status_code == 200:
                        cdx_data = res.json()
                        # Reverse so oldest first
                        cdx_sorted = sorted(cdx_data, key=lambda x: x["time"])
                        candles = [
                            {
                                "time": c["time"],
                                "open": float(c["open"]),
                                "high": float(c["high"]),
                                "low": float(c["low"]),
                                "close": float(c["close"]),
                                "volume": float(c["volume"]),
                            }
                            for c in cdx_sorted
                        ]
                        return candles
            except Exception as exc:
                log.warning("coindcx_fetch_candles_error", error=str(exc))

        if not raw_candles:
            raise RuntimeError(f"Unable to fetch candles for symbol {symbol}")

        # Resample base candles into target timeframe (e.g. 90m)
        resampled: List[Dict[str, Any]] = []
        n = len(raw_candles)

        for i in range(0, n, chunk_size):
            chunk = raw_candles[i : i + chunk_size]
            if not chunk:
                continue
            o_time = chunk[0][0]
            c_open = float(chunk[0][1])
            c_high = max(float(x[2]) for x in chunk)
            c_low = min(float(x[3]) for x in chunk)
            c_close = float(chunk[-1][4])
            c_vol = sum(float(x[5]) for x in chunk)
            resampled.append({
                "time": o_time,
                "open": c_open,
                "high": c_high,
                "low": c_low,
                "close": c_close,
                "volume": c_vol,
            })

        return resampled

    @classmethod
    def calculate_supertrend(
        cls,
        candles: List[Dict[str, Any]],
        period: int = 16,
        multiplier: float = 1.5,
    ) -> Dict[str, Any]:
        """
        Calculate SuperTrend indicator on OHLCV candles using Wilder's RMA ATR.
        Returns:
            {
                "current_spot": float,
                "supertrend": float,
                "signal": "GREEN" | "RED",
                "prev_signal": "GREEN" | "RED",
                "did_flip": bool,
                "timestamp": int
            }
        """
        if len(candles) < period + 2:
            raise ValueError(f"Insufficient candles ({len(candles)}) for SuperTrend period {period}")

        n = len(candles)

        # 1. True Range (TR)
        tr_list = []
        for i in range(n):
            h = candles[i]["high"]
            l = candles[i]["low"]
            if i == 0:
                tr = h - l
            else:
                prev_c = candles[i - 1]["close"]
                tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)

        # 2. ATR via Wilder's RMA (standard TradingView SuperTrend calculation)
        atr: List[Optional[float]] = [None] * n
        # Initial ATR: simple average of first `period` TRs
        initial_atr = sum(tr_list[:period]) / period
        atr[period - 1] = initial_atr
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr_list[i]) / period

        # 3. Basic Upper & Lower Bands
        basic_upper: List[Optional[float]] = [None] * n
        basic_lower: List[Optional[float]] = [None] * n
        for i in range(n):
            if atr[i] is not None:
                hl2 = (candles[i]["high"] + candles[i]["low"]) / 2.0
                basic_upper[i] = hl2 + (multiplier * atr[i])
                basic_lower[i] = hl2 - (multiplier * atr[i])

        # 4. Final Upper & Lower Bands and SuperTrend Direction
        final_upper = [0.0] * n
        final_lower = [0.0] * n
        supertrend = [0.0] * n
        direction = [1] * n  # 1 = Bullish (Green), -1 = Bearish (Red)

        for i in range(n):
            if atr[i] is None:
                continue

            close = candles[i]["close"]
            bu = basic_upper[i]
            bl = basic_lower[i]

            if i == 0 or atr[i - 1] is None:
                final_upper[i] = bu
                final_lower[i] = bl
                supertrend[i] = bu
                direction[i] = 1
                continue

            prev_fu = final_upper[i - 1]
            prev_fl = final_lower[i - 1]
            prev_close = candles[i - 1]["close"]

            # Final upper band
            if bu < prev_fu or prev_close > prev_fu:
                final_upper[i] = bu
            else:
                final_upper[i] = prev_fu

            # Final lower band
            if bl > prev_fl or prev_close < prev_fl:
                final_lower[i] = bl
            else:
                final_lower[i] = prev_fl

            # SuperTrend & Direction evaluation
            prev_dir = direction[i - 1]

            if prev_dir == 1:  # Bullish state
                if close < final_lower[i]:
                    direction[i] = -1  # Flip to Bearish (Red)
                    supertrend[i] = final_upper[i]
                else:
                    direction[i] = 1
                    supertrend[i] = final_lower[i]
            else:  # Bearish state
                if close > final_upper[i]:
                    direction[i] = 1  # Flip to Bullish (Green)
                    supertrend[i] = final_lower[i]
                else:
                    direction[i] = -1
                    supertrend[i] = final_upper[i]

        latest = candles[-1]
        latest_signal = "GREEN" if direction[-1] == 1 else "RED"
        prev_signal = "GREEN" if direction[-2] == 1 else "RED"
        did_flip = latest_signal != prev_signal

        return {
            "current_spot": latest["close"],
            "supertrend": supertrend[-1],
            "signal": latest_signal,
            "prev_signal": prev_signal,
            "did_flip": did_flip,
            "candle_time": latest["time"],
        }

    @classmethod
    async def get_indicator_status(
        cls,
        symbol: str = "BTCUSD",
        timeframe: str = "90m",
        period: int = 16,
        multiplier: float = 1.5,
    ) -> Dict[str, Any]:
        """Helper to get live status without altering rule state."""
        minutes = cls.parse_timeframe_to_minutes(timeframe)
        candles = await cls.fetch_candles(symbol, timeframe_minutes=minutes, limit_candles=100)
        calc = cls.calculate_supertrend(candles, period=period, multiplier=multiplier)
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "period": period,
            "multiplier": multiplier,
            "current_spot": round(calc["current_spot"], 4),
            "supertrend": round(calc["supertrend"], 4),
            "signal": calc["signal"],
            "prev_signal": calc["prev_signal"],
            "did_flip": calc["did_flip"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def parse_timeframe_to_minutes(cls, tf: str) -> int:
        """Parse '90m', '90 mins', '1h', '4h', '15m' to integer minutes."""
        tf_str = tf.lower().replace("mins", "m").replace("min", "m").replace("hours", "h").replace("hour", "h").strip()
        if "h" in tf_str:
            num = float(tf_str.replace("h", "").strip() or 1)
            return int(num * 60)
        elif "m" in tf_str:
            return int(float(tf_str.replace("m", "").strip() or 1))
        elif tf_str.isdigit():
            return int(tf_str)
        return 90

    @classmethod
    async def evaluate_rule(
        cls,
        rule: AlertRule,
        session: AsyncSession,
        force_notify: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate a single alert rule against live market data.
        If signal flipped (or force_notify is True), dispatches Telegram alert.
        """
        params = rule.params or {"period": 16, "multiplier": 1.5}
        period = int(params.get("period", 16))
        multiplier = float(params.get("multiplier", 1.5))
        tf_mins = cls.parse_timeframe_to_minutes(rule.timeframe)

        # 1. Fetch live candles and calculate SuperTrend
        candles = await cls.fetch_candles(rule.symbol, timeframe_minutes=tf_mins)
        calc = cls.calculate_supertrend(candles, period=period, multiplier=multiplier)

        new_signal = calc["signal"]
        old_signal = rule.current_signal
        spot_price = float(calc["current_spot"])
        st_value = float(calc["supertrend"])
        now = datetime.now(timezone.utc)

        # Check if flipped:
        # A true flip ONLY occurs when transitioning between different states (e.g. RED -> GREEN or GREEN -> RED)
        did_flip = (old_signal is not None and old_signal != new_signal)

        # Update rule state
        rule.current_spot = Decimal(str(spot_price))
        rule.current_value = Decimal(str(st_value))
        rule.current_signal = new_signal
        rule.last_checked_at = now

        notification_result = None

        if did_flip or force_notify:
            rule.last_flip_at = now
            effective_old_signal = old_signal
            if force_notify and not did_flip:
                # If manually simulating a flip, show flip from opposite signal
                effective_old_signal = "RED" if new_signal == "GREEN" else "GREEN"

            log.info(
                "alert_signal_flip_detected",
                rule_id=rule.id,
                symbol=rule.symbol,
                old_signal=effective_old_signal,
                new_signal=new_signal,
                spot=spot_price,
                st=st_value,
                force_notify=force_notify,
            )

            if rule.notify_telegram:
                # Format message
                timeframe_label = f"{tf_mins} mins" if "m" in rule.timeframe else rule.timeframe
                msg_text = TelegramService.format_supertrend_alert(
                    symbol=rule.symbol,
                    old_signal=effective_old_signal,
                    new_signal=new_signal,
                    spot_price=spot_price,
                    indicator_value=st_value,
                    timeframe=timeframe_label,
                    params=params,
                )

                # Send via Telegram
                send_res = await TelegramService.send_message(
                    text=msg_text,
                    chat_id=rule.telegram_chat_id,
                )
                notification_result = send_res

                # Record notification in DB
                notif = AlertNotification(
                    rule_id=rule.id,
                    user_id=rule.user_id,
                    symbol=rule.symbol,
                    event_type="SIGNAL_FLIP" if did_flip else "MANUAL_TEST",
                    old_signal=effective_old_signal,
                    new_signal=new_signal,
                    spot_price=Decimal(str(spot_price)),
                    indicator_value=Decimal(str(st_value)),
                    message_text=msg_text,
                    channel="TELEGRAM",
                    status="SENT" if send_res.get("success") else "FAILED",
                    error_message=send_res.get("error"),
                )
                session.add(notif)

        await session.commit()

        return {
            "rule_id": rule.id,
            "symbol": rule.symbol,
            "signal": new_signal,
            "old_signal": old_signal,
            "did_flip": did_flip,
            "current_spot": spot_price,
            "supertrend": st_value,
            "telegram_sent": notification_result.get("success") if notification_result else False,
            "notification": notification_result,
            "checked_at": now.isoformat(),
        }

    @classmethod
    async def evaluate_all_active_rules(cls, session: AsyncSession) -> List[Dict[str, Any]]:
        """Evaluate all active alert rules."""
        res = await session.execute(
            select(AlertRule).where(AlertRule.is_active.is_(True))
        )
        rules = res.scalars().all()
        results = []
        for r in rules:
            try:
                res_rule = await cls.evaluate_rule(r, session)
                results.append(res_rule)
            except Exception as exc:
                log.error("evaluate_rule_failed", rule_id=r.id, error=str(exc))
                results.append({"rule_id": r.id, "error": str(exc)})
        return results

