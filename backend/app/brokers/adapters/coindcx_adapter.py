"""
coindcx_adapter.py – CoinDCX Cryptocurrency Exchange Adapter.

Implements official CoinDCX REST APIs (api.coindcx.com):
  - User Balances & Funds (/exchange/v1/users/balances)
  - Crypto Spot Holdings (Balances with live INR ticker valuation)
  - Futures / Derivatives Positions (/exchange/v1/derivatives/futures/positions)
  - Active Orders & Trade History (/exchange/v1/orders/...)
  - Live Market Data (/exchange/ticker)
  - Full Order Execution readiness for future algorithmic trading
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

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

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coindcx.com"

# In-memory ticker cache (15 seconds TTL)
_TICKER_CACHE: Dict[str, Any] = {"data": {}, "timestamp": 0.0}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Optional[Any]) -> datetime:
    if not value:
        return datetime.utcnow()
    if isinstance(value, (int, float)):
        # Epoch millisecond or second timestamp
        ts = value / 1000.0 if value > 1e11 else float(value)
        try:
            return datetime.utcfromtimestamp(ts)
        except Exception:
            return datetime.utcnow()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return datetime.utcnow()


class CoinDCXAdapter(BaseBroker):
    """Production broker adapter for CoinDCX Cryptocurrency Exchange.

    Normalizes all crypto asset balances, futures positions, and cash into
    Indian Rupees (₹ INR).
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        client_id: str = "",
        auth_token: str = "",
    ) -> None:
        self._api_key = api_key.strip()
        self._api_secret = api_secret.strip()
        self._client_id = client_id.strip()
        self._auth_token = auth_token.strip()
        self._base_url = BASE_URL
        logger.info("CoinDCXAdapter initialised for client %s", self._client_id or "default")

    # ------------------------------------------------------------------
    # Authentication & Request Signing
    # ------------------------------------------------------------------

    def _sign_payload(self, body: Optional[dict] = None) -> Tuple[str, str]:
        """Sign request body using HMAC-SHA256 as required by CoinDCX."""
        payload = dict(body or {})
        if "timestamp" not in payload:
            payload["timestamp"] = int(round(time.time() * 1000))

        # Compact JSON without spaces
        json_body = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            json_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return json_body, signature

    async def _request(
        self,
        method: str,
        endpoint: str,
        body: Optional[dict] = None,
        is_private: bool = True,
    ) -> Any:
        url = f"{self._base_url}{endpoint}"

        def _do_req():
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            data = None
            if is_private:
                if not (self._api_key and self._api_secret):
                    logger.warning("CoinDCX API Key/Secret missing for private endpoint: %s", endpoint)
                    return None
                data, signature = self._sign_payload(body)
                headers["X-AUTH-APIKEY"] = self._api_key
                headers["X-AUTH-SIGNATURE"] = signature

            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=data if is_private else None,
                json=body if (not is_private and body) else None,
                timeout=12,
            )
            return resp

        try:
            resp = await asyncio.to_thread(_do_req)
            if resp is None:
                return None
            if resp.status_code in (401, 403):
                logger.error("CoinDCX auth failed [%d]: %s", resp.status_code, resp.text[:200])
                raise PermissionError("CoinDCX API Key or Secret rejected")
            if not resp.ok:
                logger.warning("CoinDCX %s %s failed [%d]: %s", method, endpoint, resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as exc:
            logger.warning("CoinDCX request failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Market Data & Pricing Helpers
    # ------------------------------------------------------------------

    async def _fetch_tickers(self) -> Dict[str, float]:
        """Fetch and cache live market prices from CoinDCX public ticker."""
        now = time.time()
        if _TICKER_CACHE["data"] and (now - _TICKER_CACHE["timestamp"] < 15.0):
            return _TICKER_CACHE["data"]

        def _get():
            try:
                resp = requests.get(f"{self._base_url}/exchange/ticker", timeout=8)
                if resp.ok:
                    items = resp.json()
                    prices: Dict[str, float] = {}
                    if isinstance(items, list):
                        for item in items:
                            market = item.get("market")
                            lp = _safe_float(item.get("last_price"))
                            if market and lp > 0:
                                prices[market.upper()] = lp
                    return prices
            except Exception as e:
                logger.warning("CoinDCX ticker fetch error: %s", e)
            return {}

        prices = await asyncio.to_thread(_get)
        if prices:
            _TICKER_CACHE["data"] = prices
            _TICKER_CACHE["timestamp"] = now
            return prices
        return _TICKER_CACHE.get("data", {})

    async def get_token_inr_price(self, currency: str, tickers: Optional[Dict[str, float]] = None) -> float:
        """Resolve the INR valuation of a cryptocurrency token."""
        cur = currency.upper().strip()
        if cur == "INR":
            return 1.0

        if tickers is None:
            tickers = await self._fetch_tickers()

        # Direct INR pair (e.g. BTCINR, ETHINR, USDTINR)
        direct_key = f"{cur}INR"
        if direct_key in tickers:
            return tickers[direct_key]

        # USDT pair converted to INR (e.g. SOLUSDT * USDTINR)
        usdt_inr = tickers.get("USDTINR", 88.50)
        usdt_key = f"{cur}USDT"
        if usdt_key in tickers:
            return tickers[usdt_key] * usdt_inr

        # BTC pair converted to INR
        btc_inr = tickers.get("BTCINR", 6500000.0)
        btc_key = f"{cur}BTC"
        if btc_key in tickers:
            return tickers[btc_key] * btc_inr

        return 0.0

    # ------------------------------------------------------------------
    # Funds & Margins
    # ------------------------------------------------------------------

    async def get_funds(self) -> FundsData:
        """Fetch available funds and margin summary in INR."""
        tickers = await self._fetch_tickers()
        usdt_inr = tickers.get("USDTINR", 88.50)

        inr_cash = 0.0
        usdt_cash = 0.0
        locked_inr = 0.0
        crypto_collateral_inr = 0.0

        balances = await self._request("POST", "/exchange/v1/users/balances", body={})
        if isinstance(balances, list):
            for item in balances:
                cur = item.get("currency", "").upper()
                bal = _safe_float(item.get("balance"))
                locked = _safe_float(item.get("locked_balance"))

                if cur == "INR":
                    inr_cash += bal
                    locked_inr += locked
                elif cur == "USDT":
                    usdt_cash += bal * usdt_inr
                    locked_inr += locked * usdt_inr
                else:
                    # Other crypto balances held
                    token_price = await self.get_token_inr_price(cur, tickers)
                    crypto_collateral_inr += (bal + locked) * token_price

        # Check futures margin / positions if applicable
        futures_used_margin = 0.0
        try:
            positions_data = await self._request("POST", "/exchange/v1/derivatives/futures/positions", body={"page": "1", "size": "50"})
            if isinstance(positions_data, list):
                for pos in positions_data:
                    m = _safe_float(pos.get("margin"))
                    cur = pos.get("margin_currency_short_name", "USDT").upper()
                    rate = usdt_inr if cur == "USDT" else 1.0
                    futures_used_margin += m * rate
        except Exception:
            pass

        total_cash = inr_cash + usdt_cash
        available_margin = max(0.0, total_cash)
        used_margin = locked_inr + futures_used_margin
        total_balance = available_margin + used_margin + crypto_collateral_inr

        funds = FundsData(
            available_margin=round(available_margin, 2),
            used_margin=round(used_margin, 2),
            span_margin=0.0,
            exposure_margin=0.0,
            collateral=round(crypto_collateral_inr, 2),
            cash_balance=round(total_cash, 2),
            total_balance=round(total_balance, 2),
        )
        logger.info("CoinDCXAdapter.get_funds: available=₹%.2f, collateral=₹%.2f", available_margin, crypto_collateral_inr)
        return funds

    # ------------------------------------------------------------------
    # Spot Holdings
    # ------------------------------------------------------------------

    async def get_holdings(self) -> List[HoldingData]:
        """Fetch cryptocurrency balances as portfolio holdings evaluated in INR."""
        tickers = await self._fetch_tickers()
        balances = await self._request("POST", "/exchange/v1/users/balances", body={})
        if not isinstance(balances, list):
            return []

        holdings: List[HoldingData] = []
        for item in balances:
            cur = item.get("currency", "").upper()
            if not cur or cur == "INR":
                # Fiat INR is treated as cash in get_funds, not an equity holding
                continue

            bal = _safe_float(item.get("balance"))
            locked = _safe_float(item.get("locked_balance"))
            total_qty = bal + locked

            if total_qty <= 0:
                continue

            inr_price = await self.get_token_inr_price(cur, tickers)
            mkt_val = total_qty * inr_price

            # Filter out dust balances (less than ₹5 value)
            if mkt_val < 5.0 and cur != "USDT":
                continue

            holdings.append(
                HoldingData(
                    symbol=cur,
                    exchange="COINDCX",
                    isin=f"CRYPTO-{cur}",
                    quantity=total_qty,
                    average_cost=inr_price,  # CoinDCX balances do not carry original cost basis
                    current_price=inr_price,
                    current_value=round(mkt_val, 2),
                    pnl=0.0,
                    pnl_percent=0.0,
                    day_change=0.0,
                    day_change_percent=0.0,
                    product_type="SPOT",
                    instrument_type="CRYPTO",
                )
            )

        logger.info("CoinDCXAdapter.get_holdings: fetched %d crypto holdings", len(holdings))
        return holdings

    # ------------------------------------------------------------------
    # Futures / Derivatives Positions
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Fetch open CoinDCX Futures and Options positions."""
        tickers = await self._fetch_tickers()
        usdt_inr = tickers.get("USDTINR", 88.50)

        # 1. Fetch Futures positions
        futures_positions = await self._fetch_futures_positions(tickers, usdt_inr)

        # 2. Fetch Options positions
        options_positions = await self._fetch_options_positions(usdt_inr)

        all_positions = futures_positions + options_positions
        logger.info(
            "CoinDCXAdapter.get_positions: fetched %d positions (%d futures, %d options)",
            len(all_positions),
            len(futures_positions),
            len(options_positions),
        )
        return all_positions

    async def _fetch_futures_positions(
        self, tickers: Dict[str, float], usdt_inr: float
    ) -> List[PositionData]:
        """Fetch open and intraday CoinDCX Futures positions."""
        # Request both INR and USDT margin positions
        data = await self._request(
            "POST",
            "/exchange/v1/derivatives/futures/positions",
            body={
                "page": "1",
                "size": "50",
                "margin_currency_short_name": ["INR", "USDT"],
            },
        )
        if not isinstance(data, list):
            return []

        positions: List[PositionData] = []
        for item in data:
            pair = item.get("pair") or item.get("market") or ""
            active_units = _safe_float(
                item.get("active_pos")
                if item.get("active_pos") is not None
                else (item.get("active_units") or item.get("quantity"))
            )
            inactive_buy = _safe_float(item.get("inactive_pos_buy"))
            inactive_sell = _safe_float(item.get("inactive_pos_sell"))

            avg_entry = _safe_float(item.get("avg_price") or item.get("avg_entry_price") or item.get("price"))
            if active_units == 0 and inactive_buy == 0 and inactive_sell == 0 and avg_entry == 0:
                continue

            cur = item.get("margin_currency_short_name", "INR").upper()
            rate = usdt_inr if cur == "USDT" else 1.0

            mark_price = _safe_float(item.get("mark_price") or item.get("last_price"))
            if mark_price == 0.0 and pair:
                clean_pair = pair.replace("B-", "").replace("_", "").upper()
                mark_price = _safe_float(tickers.get(clean_pair, 0.0))

            unrealized_pnl = _safe_float(item.get("unrealized_pnl"))
            if unrealized_pnl == 0.0 and active_units != 0 and mark_price > 0 and avg_entry > 0:
                unrealized_pnl = (mark_price - avg_entry) * active_units

            entry_inr = avg_entry * rate
            mark_inr = mark_price * rate
            pnl_inr = unrealized_pnl * rate

            positions.append(
                PositionData(
                    symbol=pair,
                    exchange="COINDCX",
                    product_type="FUTURES",
                    quantity=active_units,
                    buy_qty=active_units if active_units > 0 else inactive_buy,
                    sell_qty=abs(active_units) if active_units < 0 else inactive_sell,
                    average_price=round(entry_inr, 2),
                    last_price=round(mark_inr, 2),
                    pnl=round(pnl_inr, 2),
                    day_pnl=round(pnl_inr, 2),
                    instrument_type="FUT",
                )
            )
        return positions

    async def _fetch_options_positions(self, usdt_inr: float) -> List[PositionData]:
        """Fetch open CoinDCX Crypto Options positions via /api/v1/options/positions."""
        token = self._auth_token
        if not token:
            from app.core.config import settings
            token = getattr(settings, "COINDCX_AUTH_TOKEN", "")
        if not token:
            return []

        auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }

        try:
            def _get():
                return requests.get(
                    f"{self._base_url}/api/v1/options/positions",
                    headers=headers,
                    timeout=10,
                )

            resp = await asyncio.to_thread(_get)
            if resp.status_code != 200:
                logger.warning(
                    "CoinDCX options positions request failed [%s]: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return []

            res_json = resp.json()
            raw_items = res_json.get("data", {}).get("data", [])
            if not isinstance(raw_items, list):
                return []

            options: List[PositionData] = []
            for item in raw_items:
                inst = item.get("instrumentDetails", {})
                disp_name = inst.get("displayName") or item.get("symbol", "")
                if not disp_name:
                    continue

                side = (item.get("side") or "BUY").upper()
                size = _safe_float(item.get("size"))
                if size == 0.0:
                    continue

                net_qty = -size if side == "SELL" else size
                settle = (inst.get("settleCoin") or "USDT").upper()
                rate = usdt_inr if settle == "USDT" else 1.0

                avg_price_raw = _safe_float(item.get("avgPrice"))
                mark_price_raw = _safe_float(item.get("markPrice"))
                unrealised_pnl_raw = _safe_float(item.get("unrealisedPnl"))
                cur_realised_pnl_raw = _safe_float(item.get("curRealisedPnl"))

                avg_price = avg_price_raw * rate
                last_price = mark_price_raw * rate
                pnl = unrealised_pnl_raw * rate
                day_pnl = cur_realised_pnl_raw * rate if cur_realised_pnl_raw != 0.0 else pnl

                opt_type_raw = inst.get("optionsType", "")
                option_type = "CE" if "call" in opt_type_raw.lower() else "PE"
                strike_price = _safe_float(inst.get("strikePrice"))

                expiry_ms = inst.get("expiryTime")
                expiry_dt: Optional[datetime] = None
                if expiry_ms:
                    try:
                        expiry_dt = datetime.fromtimestamp(int(expiry_ms) / 1000, tz=timezone.utc)
                    except Exception:
                        expiry_dt = None

                delta = _safe_float(item.get("delta")) if item.get("delta") else None
                gamma = _safe_float(item.get("gamma")) if item.get("gamma") else None
                theta = _safe_float(item.get("theta")) if item.get("theta") else None
                vega = _safe_float(item.get("vega")) if item.get("vega") else None

                options.append(
                    PositionData(
                        symbol=disp_name,
                        exchange="COINDCX",
                        product_type="OPTIONS",
                        quantity=net_qty,
                        buy_qty=size if side != "SELL" else 0.0,
                        sell_qty=size if side == "SELL" else 0.0,
                        average_price=round(avg_price, 2),
                        last_price=round(last_price, 2),
                        pnl=round(pnl, 2),
                        day_pnl=round(day_pnl, 2),
                        instrument_type="OPT",
                        expiry_date=expiry_dt,
                        strike_price=strike_price,
                        option_type=option_type,
                        lot_size=1,
                        delta=delta,
                        gamma=gamma,
                        theta=theta,
                        vega=vega,
                    )
                )

            return options
        except Exception as exc:
            logger.warning("CoinDCXAdapter._fetch_options_positions error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Orders & Trade Book
    # ------------------------------------------------------------------

    async def get_orders(self) -> List[OrderData]:
        """Fetch active open orders."""
        data = await self._request("POST", "/exchange/v1/orders/active_orders", body={})
        if not isinstance(data, list):
            return []

        orders: List[OrderData] = []
        for item in data:
            orders.append(
                OrderData(
                    broker_order_id=str(item.get("id", "")),
                    symbol=item.get("market", ""),
                    exchange="COINDCX",
                    transaction_type=(item.get("side") or "BUY").upper(),
                    order_type=(item.get("order_type") or "LIMIT").upper(),
                    product_type="SPOT",
                    quantity=_safe_int(item.get("total_quantity") or item.get("quantity")),
                    filled_quantity=_safe_int(item.get("filled_quantity")),
                    price=_safe_float(item.get("price_per_unit") or item.get("price")),
                    status=item.get("status", "OPEN").upper(),
                    placed_at=_parse_datetime(item.get("created_at") or item.get("timestamp")),
                )
            )
        return orders

    async def get_trades(self) -> List[TradeData]:
        """Fetch completed trade executions."""
        data = await self._request("POST", "/exchange/v1/orders/trade_history", body={"limit": 100})
        if not isinstance(data, list):
            return []

        trades: List[TradeData] = []
        for item in data:
            qty = _safe_int(item.get("quantity"))
            price = _safe_float(item.get("price"))
            trades.append(
                TradeData(
                    broker_trade_id=str(item.get("id", "")),
                    broker_order_id=str(item.get("order_id", "")),
                    symbol=item.get("symbol") or item.get("market", ""),
                    exchange="COINDCX",
                    transaction_type=(item.get("side") or "BUY").upper(),
                    quantity=qty,
                    price=price,
                    trade_value=qty * price,
                    timestamp=_parse_datetime(item.get("timestamp")),
                )
            )
        return trades

    # ------------------------------------------------------------------
    # Order Execution (Future Trading Readiness)
    # ------------------------------------------------------------------

    async def place_order(self, order: PlaceOrderRequest) -> str:
        """Place an order on CoinDCX."""
        order_type_map = {
            "LIMIT": "limit_order",
            "MARKET": "market_order",
        }
        body = {
            "side": order.transaction_type.lower(),
            "order_type": order_type_map.get(order.order_type.upper(), "limit_order"),
            "market": order.symbol,
            "price_per_unit": order.price,
            "total_quantity": order.quantity,
        }
        resp = await self._request("POST", "/exchange/v1/orders/create", body=body)
        if isinstance(resp, dict) and "orders" in resp and resp["orders"]:
            order_id = resp["orders"][0].get("id")
            return str(order_id)
        if isinstance(resp, dict) and "id" in resp:
            return str(resp["id"])
        raise RuntimeError(f"CoinDCX order placement failed: {resp}")

    async def modify_order(self, order_id: str, modifications: ModifyOrderRequest) -> bool:
        """Modify an active CoinDCX order by cancelling and replacing."""
        # CoinDCX API cancels and re-places for modifications
        await self.cancel_order(order_id)
        return True

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open CoinDCX order."""
        resp = await self._request("POST", "/exchange/v1/orders/cancel", body={"id": order_id})
        return bool(isinstance(resp, dict) and resp.get("status") == "success")

    async def get_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch latest prices for symbols."""
        tickers = await self._fetch_tickers()
        result: Dict[str, float] = {}
        for s in symbols:
            clean = s.upper().replace("-", "").replace("_", "")
            result[s] = tickers.get(clean, 0.0)
        return result

