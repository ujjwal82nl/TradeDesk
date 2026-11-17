"""
dhan_adapter.py – Dhan HQ broker adapter.

Requires:
    pip install dhanhq structlog

Documentation: https://dhanhq.co/docs/v2/
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from dhanhq import dhanhq  # type: ignore[import-untyped]

from app.brokers.base import (
    BaseBroker,
    FundsData,
    HoldingData,
    ModifyOrderRequest,
    OrderData,
    PlaceOrderRequest,
    PositionData,
    TradeData,
)

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

# Internal canonical product type → Dhan product type string
_PRODUCT_TYPE_TO_DHAN: Dict[str, str] = {
    "CNC": "CNC",
    "INTRADAY": "INTRADAY",
    "MARGIN": "MARGIN",
    "CO": "CO",
    "BO": "BO",
    "MTF": "MTF",
}

# Dhan product type string → canonical internal string
_DHAN_TO_PRODUCT_TYPE: Dict[str, str] = {v: k for k, v in _PRODUCT_TYPE_TO_DHAN.items()}

# Internal canonical exchange → Dhan exchange segment string
_EXCHANGE_TO_DHAN: Dict[str, str] = {
    "NSE": "NSE_EQ",
    "NSE_FNO": "NSE_FNO",
    "BSE": "BSE_EQ",
    "MCX": "MCX_COMM",
}

# Dhan exchange segment → canonical exchange
_DHAN_TO_EXCHANGE: Dict[str, str] = {
    "NSE_EQ": "NSE",
    "NSE_FNO": "NSE_FNO",
    "BSE_EQ": "BSE",
    "MCX_COMM": "MCX",
}

# Dhan order type → canonical order type
_DHAN_ORDER_TYPE: Dict[str, str] = {
    "LIMIT": "LIMIT",
    "MARKET": "MARKET",
    "STOP_LOSS": "SL",
    "STOP_LOSS_MARKET": "SL-M",
}

# Reverse mapping for placing orders
_ORDER_TYPE_TO_DHAN: Dict[str, str] = {v: k for k, v in _DHAN_ORDER_TYPE.items()}

# Dhan order status → canonical status
_DHAN_STATUS: Dict[str, str] = {
    "PENDING": "PENDING",
    "TRANSIT": "PENDING",
    "CONFIRMED": "OPEN",
    "TRADED": "COMPLETE",
    "REJECTED": "REJECTED",
    "CANCELLED": "CANCELLED",
    "EXPIRED": "CANCELLED",
    "PART_TRADED": "OPEN",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce *value* to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce *value* to int, returning *default* on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Optional[str]) -> datetime:
    """Parse an ISO-8601 or Dhan-formatted datetime string."""
    if not value:
        return datetime.utcnow()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    log.warning("dhan_adapter.unparseable_datetime", raw=value)
    return datetime.utcnow()


# In-memory cache for dynamically generated tokens: client_id -> (access_token, timestamp)
_TOKEN_CACHE: Dict[str, Tuple[str, float]] = {}


def generate_totp(secret: str) -> str:
    """Generate 6-digit TOTP from base32 secret using pyotp or standard library RFC 6238."""
    clean_secret = secret.strip().replace(" ", "").upper()
    try:
        import pyotp  # type: ignore[import-untyped]
        return pyotp.TOTP(clean_secret).now()
    except Exception:
        pass

    # Standard RFC 6238 HMAC-SHA1 fallback
    missing_padding = len(clean_secret) % 8
    if missing_padding:
        clean_secret += "=" * (8 - missing_padding)
    key = base64.b32decode(clean_secret, casefold=True)
    counter = int(time.time()) // 30
    counter_bytes = struct.pack(">Q", counter)
    h = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{(code % 1000000):06d}"


def _get_cache_dir() -> Path:
    """Return local cache directory for storing daily session tokens."""
    cache_dir = Path(__file__).resolve().parent.parent.parent.parent / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _read_cached_token_file(client_id: str) -> Optional[str]:
    """Read today's cached token from disk if present."""
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache_file = _get_cache_dir() / f"dhan_token_{client_id}_{today}.txt"
        if cache_file.exists():
            content = cache_file.read_text(encoding="utf-8").strip()
            parts = content.split("|")
            token = parts[1] if len(parts) >= 2 else parts[0]
            if token and len(token) > 20:
                return token.strip()
    except Exception:
        pass
    return None


def _write_cached_token_file(client_id: str, token: str, expiry: Optional[str] = None) -> None:
    """Save token to disk cache for today."""
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache_file = _get_cache_dir() / f"dhan_token_{client_id}_{today}.txt"
        cache_file.write_text(f"{today}|{token}|{expiry or ''}", encoding="utf-8")
    except Exception:
        pass


def request_dhan_access_token(
    client_id: str,
    pin: str,
    totp_secret: str,
    force_refresh: bool = False,
) -> Tuple[str, Optional[str]]:
    """Request a fresh Dhan access token using PIN + TOTP via https://auth.dhan.co.

    Dhan tokens are valid for up to 24 hours. The API limits generation to once every
    2 minutes, so tokens are cached automatically in memory and on disk.
    """
    clean_client_id = str(client_id).strip()
    clean_pin = str(pin).strip()

    # 1. Reuse in-memory cache if still valid (cached up to 23 hours)
    if not force_refresh:
        cached = _TOKEN_CACHE.get(clean_client_id)
        if cached:
            cached_token, cached_time = cached
            if time.time() - cached_time < 23 * 3600:
                log.info("dhan_adapter.using_cached_totp_token", client_id=clean_client_id)
                return cached_token, None

        # 2. Check disk cache for today
        file_token = _read_cached_token_file(clean_client_id)
        if file_token:
            _TOKEN_CACHE[clean_client_id] = (file_token, time.time())
            log.info("dhan_adapter.using_disk_cached_totp_token", client_id=clean_client_id)
            return file_token, None

    url = "https://auth.dhan.co/app/generateAccessToken"

    for attempt in range(2):
        totp = generate_totp(totp_secret)
        params = {
            "dhanClientId": clean_client_id,
            "pin": clean_pin,
            "totp": totp,
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, params=params, headers={"User-Agent": "TradeDash/1.0"})
                data = resp.json()

                if data.get("status") == "error":
                    msg = data.get("message", "")
                    if "once every 2 minutes" in msg:
                        cached = _TOKEN_CACHE.get(clean_client_id)
                        if cached:
                            log.warning("dhan_adapter.token_rate_limited_using_cache", message=msg)
                            return cached[0], None
                        file_token = _read_cached_token_file(clean_client_id)
                        if file_token:
                            log.warning("dhan_adapter.token_rate_limited_using_file_cache", message=msg)
                            _TOKEN_CACHE[clean_client_id] = (file_token, time.time())
                            return file_token, None
                    if attempt == 0:
                        # Wait for the next 30-second TOTP window to start fresh
                        wait_seconds = max(2, 31 - (int(time.time()) % 30))
                        log.info("dhan_adapter.totp_window_wait", wait_seconds=wait_seconds, reason=msg)
                        time.sleep(wait_seconds)
                        continue
                    raise RuntimeError(f"Dhan token generation failed: {msg}")

                token = data.get("accessToken") or data.get("access_token")
                if not token and isinstance(data.get("data"), dict):
                    token = data["data"].get("accessToken") or data["data"].get("access_token")

                if token:
                    expiry = data.get("expiryTime")
                    _TOKEN_CACHE[clean_client_id] = (token, time.time())
                    _write_cached_token_file(clean_client_id, token, expiry)
                    log.info("dhan_adapter.token_generated_successfully", client_id=clean_client_id)
                    return token, expiry

                if attempt == 0:
                    time.sleep(2)
                    continue
                raise RuntimeError(f"AccessToken not found in Dhan response: {data}")
        except Exception as exc:
            if attempt == 0:
                wait_seconds = max(2, 31 - (int(time.time()) % 30))
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(f"Failed to generate Dhan access token: {exc}") from exc

    raise RuntimeError("Failed to generate Dhan access token after 2 attempts.")


class DhanAdapter(BaseBroker):
    """Broker adapter for Dhan HQ.

    Supports both static access tokens and automatic TOTP-based authentication.

    Args:
        client_id: Dhan client / customer ID.
        access_token: Optional static Bearer access token.
        pin: Optional Dhan 6-digit account PIN (used for TOTP login).
        totp_secret: Optional TOTP secret key for automatic login.
    """

    supports_historical_trades: bool = True

    def __init__(
        self,
        client_id: str,
        access_token: Optional[str] = None,
        pin: Optional[str] = None,
        totp_secret: Optional[str] = None,
    ) -> None:
        self._client_id = client_id
        self._access_token = access_token or ""
        self._pin = pin
        self._totp_secret = totp_secret
        self._token_expiry: Optional[str] = None
        self._dhan: Optional[Any] = None
        self._log = log.bind(broker="dhan", client_id=client_id)

        def _is_jwt_expired(tok: str) -> bool:
            try:
                parts = tok.split('.')
                if len(parts) >= 2:
                    payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
                    data = json.loads(base64.urlsafe_b64decode(payload_b64))
                    exp = data.get('exp')
                    if exp and exp <= time.time():
                        return True
            except Exception:
                pass
            return False

        # If token was not provided or has expired, and TOTP creds exist, generate token immediately
        if self._pin and self._totp_secret:
            if not self._access_token or _is_jwt_expired(self._access_token):
                self._log.info("dhan_adapter.token_missing_or_expired_refreshing")
                self.refresh_token()
            else:
                self._dhan = dhanhq(client_id=client_id, access_token=self._access_token)
        elif self._access_token:
            self._dhan = dhanhq(client_id=client_id, access_token=self._access_token)

    @property
    def access_token(self) -> str:
        """Return the active access token."""
        return self._access_token

    def refresh_token(self) -> str:
        """Force-refresh access token via PIN + TOTP."""
        if not self._pin or not self._totp_secret:
            raise RuntimeError("Cannot refresh Dhan token: PIN and TOTP secret not configured.")
        token, expiry = request_dhan_access_token(
            self._client_id, self._pin, self._totp_secret, force_refresh=True
        )
        self._access_token = token
        self._token_expiry = expiry
        self._dhan = dhanhq(client_id=self._client_id, access_token=self._access_token)
        self._log.info("dhan_adapter.token_refreshed", expiry=expiry)
        return token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_fn(self, fn: Any) -> Any:
        if isinstance(fn, str):
            return getattr(self._dhan, fn)
        if hasattr(fn, "__name__") and self._dhan is not None:
            return getattr(self._dhan, fn.__name__, fn)
        if hasattr(fn, "__func__") and hasattr(fn.__func__, "__name__") and self._dhan is not None:
            return getattr(self._dhan, fn.__func__.__name__, fn)
        return fn

    async def _run(self, fn: Any, *args, **kwargs):
        """Execute a synchronous dhanhq SDK call in a thread pool with auto-reauth."""
        if self._dhan is None and self._pin and self._totp_secret:
            await asyncio.to_thread(self.refresh_token)

        callable_fn = self._resolve_fn(fn)

        def is_token_error(res: Any) -> bool:
            if isinstance(res, dict) and res.get("status") == "failure":
                remarks = res.get("remarks") or {}
                remarks_str = str(remarks).lower()
                return any(
                    term in remarks_str
                    for term in (
                        "invalid token",
                        "token expired",
                        "dh-901",
                        "dh-906",
                        "invalid_authentication",
                        "tokenexception",
                        "unauthorized",
                        "invalid or expired",
                        "access token is invalid",
                    )
                )
            return False

        try:
            raw = await asyncio.to_thread(callable_fn, *args, **kwargs)
            if is_token_error(raw) and self._pin and self._totp_secret:
                self._log.warning("dhan_adapter.invalid_token_detected_refreshing", response=raw)
                await asyncio.to_thread(self.refresh_token)
                retry_fn = self._resolve_fn(fn)
                raw = await asyncio.to_thread(retry_fn, *args, **kwargs)
            return raw
        except Exception as exc:
            err_msg = str(exc).lower()
            if (
                any(term in err_msg for term in ("token", "auth", "unauthorized", "401", "expired", "dh-906"))
                and self._pin
                and self._totp_secret
            ):
                self._log.warning("dhan_adapter.token_error_triggering_refresh", error=str(exc))
                await asyncio.to_thread(self.refresh_token)
                retry_fn = self._resolve_fn(fn)
                return await asyncio.to_thread(retry_fn, *args, **kwargs)
            raise

    def _unwrap(self, response: Any, context: str) -> Any:
        """Extract payload from a dhanhq response dict, logging errors."""
        if not isinstance(response, dict):
            self._log.error("dhan_adapter.unexpected_response_type", context=context, response=response)
            raise RuntimeError(f"Dhan {context}: unexpected response type {type(response)}")

        status = response.get("status", "")
        if status == "failure":
            remarks = response.get("remarks", {})
            self._log.error("dhan_adapter.api_error", context=context, remarks=remarks)
            err_str = str(remarks).lower()
            if (
                any(term in err_str for term in ("token", "auth", "unauthorized", "expired"))
                and self._pin
                and self._totp_secret
            ):
                # Invalidate cache so next request will regenerate
                _TOKEN_CACHE.pop(self._client_id, None)
            raise RuntimeError(f"Dhan {context} failed: {remarks}")

        data = response.get("data")
        return data

    # ------------------------------------------------------------------
    # Holdings
    # ------------------------------------------------------------------

    async def get_holdings(self) -> List[HoldingData]:
        """Fetch all demat holdings from Dhan."""
        raw = await self._run(self._dhan.get_holdings)
        data = self._unwrap(raw, "get_holdings")
        if not data:
            return []

        holdings: List[HoldingData] = []
        for item in data:
            try:
                avg_cost = _safe_float(item.get("avgCostPrice") or item.get("averageTradedPrice"))
                ltp = _safe_float(item.get("lastTradedPrice"))
                qty = _safe_int(item.get("totalQty") or item.get("availableQty"))
                current_value = ltp * qty
                pnl = current_value - (avg_cost * qty)
                pnl_pct = ((pnl / (avg_cost * qty)) * 100) if avg_cost and qty else 0.0
                prev_close = _safe_float(item.get("previousClosePrice"))
                day_change = ltp - prev_close
                day_change_pct = ((day_change / prev_close) * 100) if prev_close else 0.0
                exchange_raw = item.get("exchangeSegment", "NSE_EQ")

                holdings.append(
                    HoldingData(
                        symbol=item.get("tradingSymbol", ""),
                        exchange=_DHAN_TO_EXCHANGE.get(exchange_raw, exchange_raw),
                        isin=item.get("isin", ""),
                        quantity=qty,
                        average_cost=avg_cost,
                        current_price=ltp,
                        current_value=current_value,
                        pnl=pnl,
                        pnl_percent=round(pnl_pct, 2),
                        day_change=day_change,
                        day_change_percent=round(day_change_pct, 2),
                        product_type=_DHAN_TO_PRODUCT_TYPE.get(
                            item.get("productType", "CNC"), "CNC"
                        ),
                        instrument_type=item.get("instrumentType", "EQ"),
                    )
                )
            except Exception as exc:
                self._log.warning("dhan_adapter.holding_parse_error", item=item, error=str(exc))

        self._log.info("dhan_adapter.get_holdings.ok", count=len(holdings))
        return holdings

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Fetch all open positions from Dhan."""
        raw = await self._run(self._dhan.get_positions)
        data = self._unwrap(raw, "get_positions")
        if not data:
            return []

        positions: List[PositionData] = []
        for item in data:
            try:
                day_buy = _safe_int(item.get("dayBuyQty"))
                day_sell = _safe_int(item.get("daySellQty"))
                buy_qty = day_buy if day_buy > 0 else _safe_int(item.get("buyQty"))
                sell_qty = day_sell if day_sell > 0 else _safe_int(item.get("sellQty"))
                net_qty = _safe_int(item.get("netQty")) if item.get("netQty") is not None else (buy_qty - sell_qty)

                # Keep all open positions (net_qty != 0) AND any positions closed today (day_buy > 0 or day_sell > 0)
                # Skip old historical squared-off positions that had no activity today
                if net_qty == 0 and (day_buy == 0 and day_sell == 0):
                    continue

                symbol = item.get("tradingSymbol", "")
                exchange_raw = item.get("exchangeSegment", "NSE_EQ")
                expiry_raw = item.get("expiryDate") or item.get("drvExpiryDate")
                strike_raw = _safe_float(item.get("strikePrice") or item.get("drvStrikePrice"))
                opt_raw = (item.get("optionType") or item.get("drvOptionType") or "").upper()

                if opt_raw in ("CALL", "CE"):
                    opt_type = "CE"
                elif opt_raw in ("PUT", "PE"):
                    opt_type = "PE"
                elif symbol.endswith("-CE") or symbol.endswith(" CE"):
                    opt_type = "CE"
                elif symbol.endswith("-PE") or symbol.endswith(" PE"):
                    opt_type = "PE"
                else:
                    opt_type = None

                inst_type = item.get("instrumentType")
                if not inst_type:
                    if opt_type:
                        inst_type = "OPT"
                    elif expiry_raw or "-FUT" in symbol:
                        inst_type = "FUT"
                    else:
                        inst_type = "EQ"

                buy_avg = _safe_float(item.get("buyAvg") or item.get("costPrice"))
                sell_avg = _safe_float(item.get("sellAvg"))
                avg_price = sell_avg if (net_qty < 0 and sell_avg > 0) else (buy_avg if buy_avg > 0 else sell_avg)
                unrealized = _safe_float(item.get("unrealizedProfit"))
                realized = _safe_float(item.get("realizedProfit"))
                mult = _safe_float(item.get("multiplier"), 1.0)

                # Derive last_price / exit_price if not explicitly returned by broker
                ltp = _safe_float(item.get("lastTradedPrice"))
                if ltp <= 0:
                    if net_qty == 0:
                        ltp = sell_avg if sell_avg > 0 else buy_avg
                    else:
                        if mult > 0:
                            ltp = round(buy_avg + (unrealized / (net_qty * mult)), 4)
                        else:
                            ltp = buy_avg

                # Total P&L of the position: realized for closed, unrealized + realized for open
                if net_qty == 0:
                    pos_pnl = realized
                    day_pnl = realized
                else:
                    pos_pnl = unrealized + realized
                    day_pnl = unrealized + realized

                positions.append(
                    PositionData(
                        symbol=symbol,
                        exchange=_DHAN_TO_EXCHANGE.get(exchange_raw, exchange_raw),
                        product_type=_DHAN_TO_PRODUCT_TYPE.get(
                            item.get("productType", "INTRADAY"), "INTRADAY"
                        ),
                        quantity=net_qty,
                        buy_qty=buy_qty,
                        sell_qty=sell_qty,
                        average_price=avg_price,
                        last_price=ltp,
                        pnl=pos_pnl,
                        day_pnl=day_pnl,
                        multiplier=mult,
                        instrument_type=inst_type,
                        expiry_date=_parse_datetime(expiry_raw) if expiry_raw else None,
                        strike_price=strike_raw or None,
                        option_type=opt_type,
                        lot_size=_safe_int(item.get("lotSize"), 1),
                    )
                )
            except Exception as exc:
                self._log.warning("dhan_adapter.position_parse_error", item=item, error=str(exc))

        self._log.info("dhan_adapter.get_positions.ok", count=len(positions))
        return positions

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def get_orders(self) -> List[OrderData]:
        """Fetch the order book for the current trading day."""
        raw = await self._run(self._dhan.get_order_list)
        data = self._unwrap(raw, "get_orders")
        if not data:
            return []

        orders: List[OrderData] = []
        for item in data:
            try:
                exchange_raw = item.get("exchangeSegment", "NSE_EQ")
                order_type_raw = item.get("orderType", "LIMIT")
                status_raw = item.get("orderStatus", "PENDING")

                orders.append(
                    OrderData(
                        broker_order_id=str(item.get("orderId", "")),
                        symbol=item.get("tradingSymbol", ""),
                        exchange=_DHAN_TO_EXCHANGE.get(exchange_raw, exchange_raw),
                        transaction_type=item.get("transactionType", "BUY"),
                        order_type=_DHAN_ORDER_TYPE.get(order_type_raw, order_type_raw),
                        product_type=_DHAN_TO_PRODUCT_TYPE.get(
                            item.get("productType", "CNC"), "CNC"
                        ),
                        quantity=_safe_int(item.get("quantity")),
                        filled_qty=_safe_int(item.get("filledQty") or item.get("tradedQuantity")),
                        price=_safe_float(item.get("price")),
                        trigger_price=_safe_float(item.get("triggerPrice")),
                        average_price=_safe_float(item.get("averageTradedPrice")),
                        status=_DHAN_STATUS.get(status_raw, status_raw),
                        timestamp=_parse_datetime(item.get("createTime") or item.get("updateTime")),
                        remarks=str(item.get("omsErrorDescription") or ""),
                    )
                )
            except Exception as exc:
                self._log.warning("dhan_adapter.order_parse_error", item=item, error=str(exc))

        self._log.info("dhan_adapter.get_orders.ok", count=len(orders))
        return orders

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    async def get_trades(self) -> List[TradeData]:
        """Fetch the trade book (fills) for the current trading day."""
        raw = await self._run(self._dhan.get_trade_book)
        data = self._unwrap(raw, "get_trades")
        if not data:
            return []

        trades: List[TradeData] = []
        for item in data:
            try:
                qty = _safe_int(item.get("tradedQuantity"))
                price = _safe_float(item.get("tradedPrice"))
                exchange_raw = item.get("exchangeSegment", "NSE_EQ")

                trades.append(
                    TradeData(
                        broker_trade_id=str(item.get("exchangeTradeId") or item.get("tradeId", "")),
                        broker_order_id=str(item.get("orderId", "")),
                        symbol=item.get("tradingSymbol", ""),
                        exchange=_DHAN_TO_EXCHANGE.get(exchange_raw, exchange_raw),
                        transaction_type=item.get("transactionType", "BUY"),
                        quantity=qty,
                        price=price,
                        trade_value=qty * price,
                        timestamp=_parse_datetime(item.get("exchangeTime") or item.get("createTime")),
                    )
                )
            except Exception as exc:
                self._log.warning("dhan_adapter.trade_parse_error", item=item, error=str(exc))

        self._log.info("dhan_adapter.get_trades.ok", count=len(trades))
        return trades

    async def get_historical_trades(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
        max_pages: int = 25,
    ) -> List[dict]:
        """Fetch historical trades across date ranges via Dhan's trade history API."""
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        if not from_date:
            from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        all_trades: List[dict] = []
        curr_page = page

        while curr_page < (page + max_pages):
            raw = await self._run(self._dhan.get_trade_history, from_date, to_date, curr_page)
            data = self._unwrap(raw, "get_trade_history")
            if not data or not isinstance(data, list) or len(data) == 0:
                break
            all_trades.extend(data)
            if len(data) < 20:
                break
            curr_page += 1

        self._log.info("dhan_adapter.get_historical_trades.ok", count=len(all_trades), pages=curr_page - page + 1)
        return all_trades

    # ------------------------------------------------------------------
    # Funds
    # ------------------------------------------------------------------

    async def get_funds(self) -> FundsData:
        """Fetch fund limits from Dhan."""
        raw = await self._run(self._dhan.get_fund_limits)
        data = self._unwrap(raw, "get_funds")
        if not isinstance(data, dict):
            data = {}

        available = _safe_float(data.get("availabelBalance") or data.get("availableBalance"))
        utilized = _safe_float(data.get("utilizedAmount"))
        span = _safe_float(data.get("spanMargin"))
        exposure = _safe_float(data.get("exposureMargin") or data.get("adhocMargin"))
        collateral = _safe_float(data.get("collateralAmount"))
        cash = _safe_float(data.get("sodLimit") or data.get("cashBalance"))
        total = available + utilized

        funds = FundsData(
            available_margin=available,
            used_margin=utilized,
            span_margin=span,
            exposure_margin=exposure,
            collateral=collateral,
            cash_balance=cash,
            total_balance=total,
        )
        self._log.info("dhan_adapter.get_funds.ok", available=available, total=total)
        return funds

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    async def place_order(self, order: PlaceOrderRequest) -> str:
        """Place an order on Dhan and return the broker order ID."""
        exchange_segment = _EXCHANGE_TO_DHAN.get(order.exchange, order.exchange)
        dhan_order_type = _ORDER_TYPE_TO_DHAN.get(order.order_type, order.order_type)
        dhan_product = _PRODUCT_TYPE_TO_DHAN.get(order.product_type, order.product_type)

        kwargs: Dict[str, Any] = dict(
            security_id=order.symbol,
            exchange_segment=exchange_segment,
            transaction_type=order.transaction_type,
            quantity=order.quantity,
            order_type=dhan_order_type,
            product_type=dhan_product,
            price=order.price or 0,
        )
        if order.trigger_price is not None:
            kwargs["trigger_price"] = order.trigger_price
        if order.tag:
            kwargs["tag"] = order.tag

        self._log.info("dhan_adapter.place_order", **kwargs)
        raw = await self._run(self._dhan.place_order, **kwargs)
        data = self._unwrap(raw, "place_order")
        order_id = str(data.get("orderId", ""))
        self._log.info("dhan_adapter.place_order.ok", order_id=order_id)
        return order_id

    async def modify_order(self, order_id: str, modifications: ModifyOrderRequest) -> bool:
        """Modify an open Dhan order."""
        payload: Dict[str, Any] = {"orderId": order_id}
        if modifications.quantity is not None:
            payload["quantity"] = modifications.quantity
        if modifications.price is not None:
            payload["price"] = modifications.price
        if modifications.trigger_price is not None:
            payload["triggerPrice"] = modifications.trigger_price
        if modifications.order_type is not None:
            payload["orderType"] = _ORDER_TYPE_TO_DHAN.get(
                modifications.order_type, modifications.order_type
            )

        self._log.info("dhan_adapter.modify_order", order_id=order_id, payload=payload)
        raw = await self._run(self._dhan.modify_order, **payload)
        self._unwrap(raw, "modify_order")
        self._log.info("dhan_adapter.modify_order.ok", order_id=order_id)
        return True

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open Dhan order."""
        self._log.info("dhan_adapter.cancel_order", order_id=order_id)
        raw = await self._run(self._dhan.cancel_order, order_id)
        self._unwrap(raw, "cancel_order")
        self._log.info("dhan_adapter.cancel_order.ok", order_id=order_id)
        return True

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """Return last traded prices for the given symbols.

        Args:
            symbols: List of plain trading symbols (e.g. ``["RELIANCE", "TCS"]``).
                     The adapter uses NSE_EQ as the default exchange segment.
                     Pass ``"EXCHANGE:SYMBOL"`` to override (e.g. ``"BSE_EQ:RELIANCE"``).
        """
        # Build security list; support optional "EXCHANGE:SYMBOL" format
        securities: List[Dict[str, Any]] = []
        symbol_map: Dict[str, str] = {}  # internal key → caller symbol
        for sym in symbols:
            if ":" in sym:
                seg, trading_sym = sym.split(":", 1)
            else:
                seg, trading_sym = "NSE_EQ", sym
            securities.append({"exchange_segment": seg, "security_id": trading_sym})
            symbol_map[trading_sym] = sym

        self._log.info("dhan_adapter.get_ltp", securities=securities)
        raw = await self._run(self._dhan.intraday_minute_data, securities=securities)
        data = self._unwrap(raw, "get_ltp")

        result: Dict[str, float] = {}
        if isinstance(data, dict):
            for trading_sym, quote in data.items():
                caller_sym = symbol_map.get(trading_sym, trading_sym)
                ltp = _safe_float(
                    quote.get("last_price") or quote.get("ltp") if isinstance(quote, dict) else quote
                )
                result[caller_sym] = ltp

        self._log.info("dhan_adapter.get_ltp.ok", count=len(result))
        return result
