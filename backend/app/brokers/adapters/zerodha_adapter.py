"""
zerodha_adapter.py – Zerodha Kite Connect broker adapter.

Requires:
    pip install kiteconnect structlog

Documentation: https://kite.trade/docs/connect/v3/
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
import urllib.parse

import httpx
import pyotp
import structlog
from kiteconnect import KiteConnect  # type: ignore[import-untyped]
from kiteconnect.exceptions import KiteException, TokenException  # type: ignore[import-untyped]

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

# Canonical product type → Zerodha product type constant
_PRODUCT_TO_ZERODHA: Dict[str, str] = {
    "CNC": getattr(KiteConnect, "PRODUCT_CNC", "CNC"),
    "INTRADAY": getattr(KiteConnect, "PRODUCT_MIS", "MIS"),
    "MIS": getattr(KiteConnect, "PRODUCT_MIS", "MIS"),
    "NRML": getattr(KiteConnect, "PRODUCT_NRML", "NRML"),
    "CO": getattr(KiteConnect, "PRODUCT_CO", "CO"),
    "BO": getattr(KiteConnect, "PRODUCT_BO", "BO"),
}

# Zerodha product type → canonical
_ZERODHA_TO_PRODUCT: Dict[str, str] = {
    getattr(KiteConnect, "PRODUCT_CNC", "CNC"): "CNC",
    getattr(KiteConnect, "PRODUCT_MIS", "MIS"): "INTRADAY",
    getattr(KiteConnect, "PRODUCT_NRML", "NRML"): "NRML",
    getattr(KiteConnect, "PRODUCT_CO", "CO"): "CO",
}

# Canonical exchange → Zerodha exchange string
_EXCHANGE_TO_ZERODHA: Dict[str, str] = {
    "NSE": KiteConnect.EXCHANGE_NSE,
    "BSE": KiteConnect.EXCHANGE_BSE,
    "NSE_FNO": KiteConnect.EXCHANGE_NFO,
    "NFO": KiteConnect.EXCHANGE_NFO,
    "CDS": KiteConnect.EXCHANGE_CDS,
    "MCX": KiteConnect.EXCHANGE_MCX,
}

# Zerodha exchange → canonical
_ZERODHA_TO_EXCHANGE: Dict[str, str] = {
    KiteConnect.EXCHANGE_NSE: "NSE",
    KiteConnect.EXCHANGE_BSE: "BSE",
    KiteConnect.EXCHANGE_NFO: "NSE_FNO",
    KiteConnect.EXCHANGE_CDS: "CDS",
    KiteConnect.EXCHANGE_MCX: "MCX",
}

# Canonical order type → Zerodha order type
_ORDER_TYPE_TO_ZERODHA: Dict[str, str] = {
    "LIMIT": KiteConnect.ORDER_TYPE_LIMIT,
    "MARKET": KiteConnect.ORDER_TYPE_MARKET,
    "SL": KiteConnect.ORDER_TYPE_SL,
    "SL-M": KiteConnect.ORDER_TYPE_SLM,
}

# Zerodha order type → canonical
_ZERODHA_TO_ORDER_TYPE: Dict[str, str] = {v: k for k, v in _ORDER_TYPE_TO_ZERODHA.items()}

# Zerodha order status → canonical status
_ZERODHA_STATUS: Dict[str, str] = {
    "OPEN": "OPEN",
    "COMPLETE": "COMPLETE",
    "CANCELLED": "CANCELLED",
    "REJECTED": "REJECTED",
    "TRIGGER PENDING": "PENDING",
    "AMO REQ RECEIVED": "PENDING",
    "MODIFIED": "OPEN",
    "OPEN PENDING": "PENDING",
    "CANCEL PENDING": "PENDING",
    "VALIDATION PENDING": "PENDING",
    "PUT ORDER REQ RECEIVED": "PENDING",
}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.utcnow()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return datetime.utcnow()


# Cache for today's generated access tokens: (user_id, api_key) -> (token, YYYY-MM-DD)
_ZERODHA_TOKEN_CACHE: Dict[str, Tuple[str, str]] = {}


def generate_totp(secret: str) -> str:
    """Generate current 6-digit TOTP from base32 secret."""
    clean_secret = secret.replace(" ", "").upper()
    return pyotp.TOTP(clean_secret).now()


def request_zerodha_access_token(
    user_id: str,
    password: str,
    totp_secret: str,
    api_key: str,
    api_secret: str,
    force_refresh: bool = False,
) -> str:
    """Automated login to Zerodha Kite Connect via User ID + Password + TOTP.

    Returns the valid daily session access_token.
    """
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    cache_key = f"{user_id}_{api_key}"

    if not force_refresh and cache_key in _ZERODHA_TOKEN_CACHE:
        cached_token, cached_date = _ZERODHA_TOKEN_CACHE[cache_key]
        if cached_date == today_str and cached_token:
            return cached_token

    # Check disk cache as well
    cache_dir = Path("/tmp/zerodha_cache") if os.name != "nt" else Path(os.environ.get("TEMP", "C:/tmp")) / "zerodha_cache"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    cache_file = cache_dir / f"{user_id}_{api_key[:6]}.json"

    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                if data.get("date") == today_str and data.get("access_token"):
                    _ZERODHA_TOKEN_CACHE[cache_key] = (data["access_token"], today_str)
                    return data["access_token"]
        except Exception:
            pass

    log.info("zerodha_adapter.initiating_totp_login", user_id=user_id)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Kite-Version": "3",
    }

    with httpx.Client(headers=headers, timeout=20.0, follow_redirects=False) as client:
        # Step 1: Login with user_id and password
        login_resp = client.post(
            "https://kite.zerodha.com/api/login",
            data={"user_id": user_id, "password": password},
        )
        login_data = login_resp.json()
        if login_data.get("status") != "success":
            err = login_data.get("message", "Login failed")
            log.error("zerodha_adapter.login_failed", error=err)
            raise RuntimeError(f"Zerodha login failed: {err}")

        request_id = login_data["data"]["request_id"]

        # Step 2: 2FA TOTP submission
        totp = generate_totp(totp_secret)
        twofa_resp = client.post(
            "https://kite.zerodha.com/api/twofa",
            data={
                "user_id": user_id,
                "request_id": request_id,
                "twofa_value": totp,
                "twofa_type": "totp",
            },
        )
        twofa_data = twofa_resp.json()
        if twofa_data.get("status") != "success":
            err = twofa_data.get("message", "2FA failed")
            log.error("zerodha_adapter.twofa_failed", error=err)
            raise RuntimeError(f"Zerodha 2FA failed: {err}")

        # Step 3: Connect app authorization redirect to obtain request_token
        connect_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
        conn_resp = client.get(connect_url)

        request_token = None
        # Either 302 redirect location header or final url
        location = conn_resp.headers.get("location", "")
        if "request_token=" in location:
            parsed = urllib.parse.urlparse(location)
            params = urllib.parse.parse_qs(parsed.query)
            request_token = params.get("request_token", [None])[0]

        if not request_token:
            # If redirected, follow one step if needed
            if conn_resp.status_code in (301, 302, 303, 307):
                next_resp = client.get(location)
                loc2 = next_resp.headers.get("location", "")
                if "request_token=" in loc2:
                    parsed = urllib.parse.urlparse(loc2)
                    request_token = urllib.parse.parse_qs(parsed.query).get("request_token", [None])[0]

        if not request_token:
            log.error("zerodha_adapter.request_token_missing", response=conn_resp.text[:200])
            raise RuntimeError("Failed to obtain request_token from Zerodha Kite Connect redirect.")

        # Step 4: Exchange request_token for access_token
        kite = KiteConnect(api_key=api_key)
        session = kite.generate_session(request_token, api_secret=api_secret)
        access_token = session["access_token"]

        _ZERODHA_TOKEN_CACHE[cache_key] = (access_token, today_str)
        try:
            with open(cache_file, "w") as f:
                json.dump({"access_token": access_token, "date": today_str}, f)
        except Exception:
            pass

        log.info("zerodha_adapter.token_generated_successfully", user_id=user_id)
        return access_token


def request_zerodha_enctoken(
    user_id: str,
    password: str,
    totp_secret: str,
    force_refresh: bool = False,
) -> str:
    """Automated headless login to Zerodha Kite Web via User ID + Password + TOTP.

    Returns the valid daily session enctoken without requiring paid Kite Connect API keys.
    """
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    cache_key = f"enctoken_{user_id}"

    if not force_refresh and cache_key in _ZERODHA_TOKEN_CACHE:
        cached_token, cached_date = _ZERODHA_TOKEN_CACHE[cache_key]
        if cached_date == today_str and cached_token:
            return cached_token

    # Check disk cache as well
    cache_dir = Path("/tmp/zerodha_cache") if os.name != "nt" else Path(os.environ.get("TEMP", "C:/tmp")) / "zerodha_cache"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    cache_file = cache_dir / f"{user_id}_enctoken.json"

    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                if data.get("date") == today_str and data.get("enctoken"):
                    _ZERODHA_TOKEN_CACHE[cache_key] = (data["enctoken"], today_str)
                    return data["enctoken"]
        except Exception:
            pass

    log.info("zerodha_adapter.initiating_enctoken_login", user_id=user_id)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://kite.zerodha.com/",
    }

    with httpx.Client(headers=headers, timeout=20.0, follow_redirects=True) as client:
        # Establish session cookies
        client.get("https://kite.zerodha.com/")
        login_headers = {**headers, "X-Kite-Version": "3"}

        # Step 1: Login with user_id and password
        login_resp = client.post(
            "https://kite.zerodha.com/api/login",
            data={"user_id": user_id, "password": password},
            headers=login_headers,
        )
        login_data = login_resp.json()
        if login_data.get("status") != "success":
            err = login_data.get("message", "Login failed")
            log.error("zerodha_adapter.enctoken_login_failed", error=err)
            raise RuntimeError(f"Zerodha login failed: {err}")

        request_id = login_data["data"]["request_id"]

        # Step 2: 2FA TOTP submission
        totp = generate_totp(totp_secret)
        twofa_resp = client.post(
            "https://kite.zerodha.com/api/twofa",
            data={
                "user_id": user_id,
                "request_id": request_id,
                "twofa_value": totp,
                "twofa_type": "totp",
            },
            headers=login_headers,
        )
        twofa_data = twofa_resp.json()
        if twofa_data.get("status") != "success":
            err = twofa_data.get("message", "2FA failed")
            log.error("zerodha_adapter.enctoken_twofa_failed", error=err)
            raise RuntimeError(f"Zerodha 2FA failed: {err}")

        # Extract enctoken from cookies
        cookies = dict(client.cookies)
        enctoken = cookies.get("enctoken")
        if not enctoken:
            for cookie in client.cookies.jar:
                if cookie.name == "enctoken":
                    enctoken = cookie.value
                    break

        if not enctoken:
            log.error("zerodha_adapter.enctoken_not_found_in_cookies")
            raise RuntimeError("Zerodha 2FA succeeded but 'enctoken' cookie was not set.")

        _ZERODHA_TOKEN_CACHE[cache_key] = (enctoken, today_str)
        try:
            with open(cache_file, "w") as f:
                json.dump({"enctoken": enctoken, "date": today_str}, f)
        except Exception:
            pass

        log.info("zerodha_adapter.enctoken_login_success", user_id=user_id)
        return enctoken


class ZerodhaEnctokenClient:
    """Lightweight wrapper mimicking KiteConnect via Zerodha Kite Web OMS endpoints.

    Communicates with https://kite.zerodha.com/oms using 'Authorization: enctoken <token>'.
    """

    BASE_URL = "https://kite.zerodha.com/oms"

    def __init__(self, enctoken: str = "") -> None:
        self.enctoken = enctoken
        self._update_headers()

    def set_access_token(self, token: str) -> None:
        self.enctoken = token
        self._update_headers()

    def _update_headers(self) -> None:
        self.headers = {
            "Authorization": f"enctoken {self.enctoken}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "X-Kite-Version": "3",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        with httpx.Client(headers=self.headers, timeout=25.0) as client:
            resp = client.request(method, url, **kwargs)
            if resp.status_code in (401, 403):
                raise TokenException(f"Zerodha session expired or unauthorized (status {resp.status_code})")
            if resp.status_code != 200:
                raise KiteException(f"Zerodha request to {endpoint} returned status {resp.status_code}: {resp.text}")
            payload = resp.json()
            if payload.get("status") != "success":
                msg = payload.get("message", "Zerodha request failed")
                if any(w in msg.lower() for w in ("session", "token", "unauthorized", "login")):
                    raise TokenException(msg)
                raise KiteException(msg)
            return payload.get("data")

    def holdings(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/portfolio/holdings")
        return data if isinstance(data, list) else []

    def positions(self) -> Dict[str, Any]:
        data = self._request("GET", "/portfolio/positions")
        return data if isinstance(data, dict) else {"net": [], "day": []}

    def orders(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/orders")
        return data if isinstance(data, list) else []

    def trades(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/trades")
        return data if isinstance(data, list) else []

    def margins(self) -> Dict[str, Any]:
        data = self._request("GET", "/user/margins")
        return data if isinstance(data, dict) else {}

    def place_order(self, variety: str = "regular", **kwargs) -> str:
        data = self._request("POST", f"/orders/{variety}", data=kwargs)
        if isinstance(data, dict) and "order_id" in data:
            return str(data["order_id"])
        return str(data)

    def modify_order(self, variety: str = "regular", order_id: str = "", **kwargs) -> str:
        data = self._request("PUT", f"/orders/{variety}/{order_id}", data=kwargs)
        if isinstance(data, dict) and "order_id" in data:
            return str(data["order_id"])
        return str(data)

    def cancel_order(self, variety: str = "regular", order_id: str = "") -> str:
        data = self._request("DELETE", f"/orders/{variety}/{order_id}")
        if isinstance(data, dict) and "order_id" in data:
            return str(data["order_id"])
        return str(data)

    def ltp(self, symbols: Any) -> Dict[str, Any]:
        return {}


class ZerodhaAdapter(BaseBroker):
    """Broker adapter for Zerodha Kite with automated TOTP login.

    Supports both:
    1. Official Kite Connect SDK (API Key + API Secret + daily access_token).
    2. Headless Direct Web Session (User ID + Password + TOTP -> enctoken), requiring
       NO developer API key or paid subscription.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        api_secret: Optional[str] = None,
        user_id: Optional[str] = None,
        password: Optional[str] = None,
        totp_secret: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or ""
        self._access_token = access_token or ""
        self._api_secret = api_secret or ""
        self._user_id = user_id or ""
        self._password = password or ""
        self._totp_secret = totp_secret or ""
        self._log = log.bind(broker="zerodha", user_id=self._user_id)

        # Mode determination: If API Key & Secret are absent, use direct enctoken mode
        self._is_enctoken_mode = not bool(self._api_key and self._api_secret)
        if self._is_enctoken_mode:
            self._can_auto_login = bool(self._user_id and self._password and self._totp_secret)
        else:
            self._can_auto_login = bool(
                self._api_key and self._api_secret and self._user_id and self._password and self._totp_secret
            )

        if not self._access_token and self._can_auto_login:
            self.refresh_token()
        elif self._is_enctoken_mode:
            self._kite = ZerodhaEnctokenClient(enctoken=self._access_token)
        elif self._access_token:
            self._kite = KiteConnect(api_key=self._api_key)
            self._kite.set_access_token(self._access_token)
        else:
            self._kite = KiteConnect(api_key=self._api_key)

    @property
    def access_token(self) -> str:
        """Return the active session access token / enctoken."""
        return self._access_token

    def refresh_token(self) -> str:
        """Force-refresh access token via Zerodha automated TOTP login."""
        if not self._can_auto_login:
            raise RuntimeError(
                "Cannot refresh Zerodha token: missing user_id, password, or totp_secret."
            )

        if self._is_enctoken_mode:
            token = request_zerodha_enctoken(
                user_id=self._user_id,
                password=self._password,
                totp_secret=self._totp_secret,
                force_refresh=True,
            )
            self._access_token = token
            self._kite = ZerodhaEnctokenClient(enctoken=self._access_token)
            self._log.info("zerodha_adapter.enctoken_refreshed")
            return token
        else:
            token = request_zerodha_access_token(
                user_id=self._user_id,
                password=self._password,
                totp_secret=self._totp_secret,
                api_key=self._api_key,
                api_secret=self._api_secret,
                force_refresh=True,
            )
            self._access_token = token
            self._kite = KiteConnect(api_key=self._api_key)
            self._kite.set_access_token(self._access_token)
            self._log.info("zerodha_adapter.token_refreshed")
            return token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run(self, fn, *args, **kwargs):
        """Run a synchronous KiteConnect/EnctokenClient call in a thread pool executor."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _resolve_fn(self, fn: Any) -> Any:
        if isinstance(fn, str):
            return getattr(self._kite, fn)
        if hasattr(fn, "__name__") and self._kite is not None:
            return getattr(self._kite, fn.__name__, fn)
        if hasattr(fn, "__func__") and hasattr(fn.__func__, "__name__") and self._kite is not None:
            return getattr(self._kite, fn.__func__.__name__, fn)
        return fn

    async def _safe_run(self, fn, context: str, *args, **kwargs):
        """Execute *fn* with KiteException/TokenException handling and automatic re-authentication."""
        try:
            callable_fn = self._resolve_fn(fn)
            return await self._run(callable_fn, *args, **kwargs)
        except (KiteException, TokenException) as exc:
            err_msg = str(exc).lower()
            if (
                any(term in err_msg for term in ("token", "session", "403", "401", "unauthorized", "invalid"))
                and self._can_auto_login
            ):
                self._log.warning(
                    "zerodha_adapter.token_error_triggering_refresh", context=context, error=str(exc)
                )
                await asyncio.to_thread(self.refresh_token)
                retry_fn = self._resolve_fn(fn)
                return await self._run(retry_fn, *args, **kwargs)

            self._log.error("zerodha_adapter.kite_error", context=context, message=str(exc))
            raise RuntimeError(f"Zerodha {context} failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Holdings
    # ------------------------------------------------------------------

    async def get_holdings(self) -> List[HoldingData]:
        """Fetch all demat holdings from Zerodha."""
        data = await self._safe_run(self._kite.holdings, "get_holdings")
        if not data:
            return []

        holdings: List[HoldingData] = []
        for item in data:
            try:
                avg_cost = _safe_float(item.get("average_price"))
                ltp = _safe_float(item.get("last_price"))
                # In Zerodha, quantity may be unpledged (quantity), T1 (t1_quantity), or pledged (collateral_quantity)
                free_qty = _safe_int(item.get("quantity"))
                t1_qty = _safe_int(item.get("t1_quantity"))
                collateral_qty = _safe_int(item.get("collateral_quantity"))
                total_qty = free_qty + t1_qty + collateral_qty
                if total_qty == 0 and item.get("opening_quantity"):
                    total_qty = _safe_int(item.get("opening_quantity"))
                qty = total_qty
                current_value = ltp * qty
                pnl = current_value - (avg_cost * qty)
                pnl_pct = ((pnl / (avg_cost * qty)) * 100) if avg_cost and qty else 0.0
                prev_close = _safe_float(item.get("close_price"))
                day_change = ltp - prev_close
                day_change_pct = ((day_change / prev_close) * 100) if prev_close else 0.0
                exchange = item.get("exchange", "NSE")

                holdings.append(
                    HoldingData(
                        symbol=item.get("tradingsymbol", ""),
                        exchange=_ZERODHA_TO_EXCHANGE.get(exchange, exchange),
                        isin=item.get("isin", ""),
                        quantity=qty,
                        average_cost=avg_cost,
                        current_price=ltp,
                        current_value=current_value,
                        pnl=pnl,
                        pnl_percent=round(pnl_pct, 2),
                        day_change=day_change,
                        day_change_percent=round(day_change_pct, 2),
                        product_type=_ZERODHA_TO_PRODUCT.get(
                            item.get("product", "CNC"), "CNC"
                        ),
                        instrument_type=item.get("instrument_type", "EQ"),
                    )
                )
            except Exception as exc:
                self._log.warning("zerodha_adapter.holding_parse_error", item=item, error=str(exc))

        self._log.info("zerodha_adapter.get_holdings.ok", count=len(holdings))
        return holdings

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Fetch all open positions from Zerodha (net + day combined)."""
        raw = await self._safe_run(self._kite.positions, "get_positions")
        # In Kite, "net" contains all open positions plus any position closed today
        items = raw.get("net", []) if isinstance(raw, dict) else []

        positions: List[PositionData] = []
        for item in items:
            try:
                symbol = item.get("tradingsymbol", "")
                buy_qty = _safe_int(item.get("buy_quantity"))
                sell_qty = _safe_int(item.get("sell_quantity"))
                net_qty = _safe_int(item.get("quantity"))
                exchange = item.get("exchange", "NSE")
                expiry_raw = item.get("expiry")

                strike_price = _safe_float(item.get("strike_price")) or None
                option_type = item.get("option_type") or None
                instrument_type = item.get("instrument_type") or ("OPT" if symbol.endswith(("CE", "PE")) else ("FUT" if symbol.endswith("FUT") else "EQ"))

                if not option_type or not strike_price:
                    match = re.search(r"(\d+(?:\.\d+)?)(CE|PE)$", symbol, re.IGNORECASE)
                    if match:
                        if not strike_price:
                            strike_price = float(match.group(1))
                        if not option_type:
                            option_type = match.group(2).upper()
                        instrument_type = "OPT"

                expiry_dt = _parse_datetime(expiry_raw) if expiry_raw else None
                if not expiry_dt and instrument_type in ("OPT", "FUT"):
                    exp_match = re.search(r"(\d{2})([A-Z]{3})", symbol)
                    if exp_match:
                        try:
                            yr_suffix = exp_match.group(1)
                            mon_str = exp_match.group(2)
                            yr = 2000 + int(yr_suffix)
                            dt_str = f"28-{mon_str}-{yr}"
                            expiry_dt = datetime.strptime(dt_str, "%d-%b-%Y")
                        except Exception:
                            pass

                positions.append(
                    PositionData(
                        symbol=symbol,
                        exchange=_ZERODHA_TO_EXCHANGE.get(exchange, exchange),
                        product_type=_ZERODHA_TO_PRODUCT.get(
                            item.get("product", "MIS"), "INTRADAY"
                        ),
                        quantity=net_qty,
                        buy_qty=buy_qty,
                        sell_qty=sell_qty,
                        average_price=_safe_float(item.get("average_price") if item.get("average_price") is not None else item.get("buy_price")),
                        last_price=_safe_float(item.get("last_price")),
                        pnl=_safe_float(item.get("pnl") if item.get("pnl") is not None else item.get("unrealised")),
                        day_pnl=_safe_float(item.get("m2m") if item.get("m2m") is not None else item.get("realised")),
                        multiplier=_safe_float(item.get("multiplier"), 1.0),
                        instrument_type=instrument_type,
                        expiry_date=expiry_dt,
                        strike_price=strike_price,
                        option_type=option_type,
                        lot_size=_safe_int(item.get("lot_size"), 25 if "NIFTY" in symbol else 1),
                    )
                )
            except Exception as exc:
                self._log.warning("zerodha_adapter.position_parse_error", item=item, error=str(exc))

        self._log.info("zerodha_adapter.get_positions.ok", count=len(positions))
        return positions

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def get_orders(self) -> List[OrderData]:
        """Fetch the order book for the current session from Zerodha."""
        data = await self._safe_run(self._kite.orders, "get_orders")
        if not data:
            return []

        orders: List[OrderData] = []
        for item in data:
            try:
                exchange = item.get("exchange", "NSE")
                status_raw = item.get("status", "OPEN")

                orders.append(
                    OrderData(
                        broker_order_id=str(item.get("order_id", "")),
                        symbol=item.get("tradingsymbol", ""),
                        exchange=_ZERODHA_TO_EXCHANGE.get(exchange, exchange),
                        transaction_type=item.get("transaction_type", "BUY"),
                        order_type=_ZERODHA_TO_ORDER_TYPE.get(
                            item.get("order_type", "LIMIT"), "LIMIT"
                        ),
                        product_type=_ZERODHA_TO_PRODUCT.get(
                            item.get("product", "CNC"), "CNC"
                        ),
                        quantity=_safe_int(item.get("quantity")),
                        filled_qty=_safe_int(item.get("filled_quantity")),
                        price=_safe_float(item.get("price")),
                        trigger_price=_safe_float(item.get("trigger_price")),
                        average_price=_safe_float(item.get("average_price")),
                        status=_ZERODHA_STATUS.get(status_raw, status_raw),
                        timestamp=_parse_datetime(
                            item.get("order_timestamp") or item.get("exchange_timestamp")
                        ),
                        remarks=str(item.get("status_message") or ""),
                    )
                )
            except Exception as exc:
                self._log.warning("zerodha_adapter.order_parse_error", item=item, error=str(exc))

        self._log.info("zerodha_adapter.get_orders.ok", count=len(orders))
        return orders

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    async def get_trades(self) -> List[TradeData]:
        """Fetch the trade book (fills) for the current session."""
        data = await self._safe_run(self._kite.trades, "get_trades")
        if not data:
            return []

        trades: List[TradeData] = []
        for item in data:
            try:
                qty = _safe_int(item.get("quantity"))
                price = _safe_float(item.get("average_price") or item.get("price"))
                exchange = item.get("exchange", "NSE")

                trades.append(
                    TradeData(
                        broker_trade_id=str(item.get("trade_id", "")),
                        broker_order_id=str(item.get("order_id", "")),
                        symbol=item.get("tradingsymbol", ""),
                        exchange=_ZERODHA_TO_EXCHANGE.get(exchange, exchange),
                        transaction_type=item.get("transaction_type", "BUY"),
                        quantity=qty,
                        price=price,
                        trade_value=qty * price,
                        timestamp=_parse_datetime(
                            item.get("fill_timestamp") or item.get("exchange_timestamp")
                        ),
                    )
                )
            except Exception as exc:
                self._log.warning("zerodha_adapter.trade_parse_error", item=item, error=str(exc))

        self._log.info("zerodha_adapter.get_trades.ok", count=len(trades))
        return trades

    # ------------------------------------------------------------------
    # Funds
    # ------------------------------------------------------------------

    async def get_funds(self) -> FundsData:
        """Fetch margin / fund summary from Zerodha."""
        raw = await self._safe_run(self._kite.margins, "get_funds")
        # kite.margins() returns {"equity": {...}, "commodity": {...}}
        eq = raw.get("equity", {}) if isinstance(raw, dict) else {}
        co = raw.get("commodity", {}) if isinstance(raw, dict) else {}

        def _sum(key: str) -> float:
            return _safe_float(eq.get(key)) + _safe_float(co.get(key))

        # In Zerodha Kite, "net" represents the total effective margin available (cash + collateral - debits)
        eq_net = eq.get("net")
        co_net = co.get("net")
        if eq_net is not None:
            available = _safe_float(eq_net) + _safe_float(co_net)
        else:
            available = _safe_float(eq.get("available", {}).get("live_balance")) + \
                        _safe_float(co.get("available", {}).get("live_balance"))

        used = _safe_float(eq.get("utilised", {}).get("debits")) + \
               _safe_float(co.get("utilised", {}).get("debits"))
        span = _safe_float(eq.get("utilised", {}).get("span")) + \
               _safe_float(co.get("utilised", {}).get("span"))
        exposure = _safe_float(eq.get("utilised", {}).get("exposure")) + \
                   _safe_float(co.get("utilised", {}).get("exposure"))
        cash = _safe_float(eq.get("available", {}).get("cash")) + \
               _safe_float(co.get("available", {}).get("cash"))
        collateral = _safe_float(eq.get("available", {}).get("collateral")) + \
                     _safe_float(co.get("available", {}).get("collateral"))

        total = max(available + used, cash + collateral)
        funds = FundsData(
            available_margin=available,
            used_margin=used,
            span_margin=span,
            exposure_margin=exposure,
            collateral=collateral,
            cash_balance=cash,
            total_balance=total,
        )
        self._log.info("zerodha_adapter.get_funds.ok", available=available)
        return funds

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    async def place_order(self, order: PlaceOrderRequest) -> str:
        """Place an order via Kite Connect and return the broker order ID."""
        zerodha_exchange = _EXCHANGE_TO_ZERODHA.get(order.exchange, order.exchange)
        zerodha_product = _PRODUCT_TO_ZERODHA.get(order.product_type, order.product_type)
        zerodha_order_type = _ORDER_TYPE_TO_ZERODHA.get(order.order_type, order.order_type)
        zerodha_txn = (
            KiteConnect.TRANSACTION_TYPE_BUY
            if order.transaction_type.upper() == "BUY"
            else KiteConnect.TRANSACTION_TYPE_SELL
        )

        kwargs = dict(
            variety=KiteConnect.VARIETY_REGULAR,
            exchange=zerodha_exchange,
            tradingsymbol=order.symbol,
            transaction_type=zerodha_txn,
            quantity=order.quantity,
            product=zerodha_product,
            order_type=zerodha_order_type,
            price=order.price,
            trigger_price=order.trigger_price,
            tag=order.tag or "",
        )
        self._log.info("zerodha_adapter.place_order", symbol=order.symbol, qty=order.quantity)
        order_id = await self._safe_run(self._kite.place_order, "place_order", **kwargs)
        self._log.info("zerodha_adapter.place_order.ok", order_id=order_id)
        return str(order_id)

    async def modify_order(self, order_id: str, modifications: ModifyOrderRequest) -> bool:
        """Modify an open Zerodha order."""
        kwargs = dict(variety=KiteConnect.VARIETY_REGULAR, order_id=order_id)
        if modifications.quantity is not None:
            kwargs["quantity"] = modifications.quantity
        if modifications.price is not None:
            kwargs["price"] = modifications.price
        if modifications.trigger_price is not None:
            kwargs["trigger_price"] = modifications.trigger_price
        if modifications.order_type is not None:
            kwargs["order_type"] = _ORDER_TYPE_TO_ZERODHA.get(
                modifications.order_type, modifications.order_type
            )

        self._log.info("zerodha_adapter.modify_order", order_id=order_id)
        await self._safe_run(self._kite.modify_order, "modify_order", **kwargs)
        self._log.info("zerodha_adapter.modify_order.ok", order_id=order_id)
        return True

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open Zerodha order."""
        self._log.info("zerodha_adapter.cancel_order", order_id=order_id)
        await self._safe_run(
            self._kite.cancel_order,
            "cancel_order",
            variety=KiteConnect.VARIETY_REGULAR,
            order_id=order_id,
        )
        self._log.info("zerodha_adapter.cancel_order.ok", order_id=order_id)
        return True

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """Return last traded prices for the given symbols.

        Args:
            symbols: List of ``"EXCHANGE:SYMBOL"`` strings as required by
                     Kite Connect (e.g. ``["NSE:RELIANCE", "NSE:TCS"]``).
                     Plain symbols default to ``NSE:`` prefix.
        """
        formatted: List[str] = []
        for sym in symbols:
            if ":" not in sym:
                formatted.append(f"NSE:{sym}")
            else:
                formatted.append(sym)

        self._log.info("zerodha_adapter.get_ltp", symbols=formatted)
        raw = await self._safe_run(self._kite.ltp, "get_ltp", formatted)

        result: Dict[str, float] = {}
        if isinstance(raw, dict):
            for key, quote in raw.items():
                # key is "NSE:RELIANCE", quote is {"last_price": ..., ...}
                original_sym = key  # preserve caller format
                # Also map to the plain symbol if caller passed without exchange prefix
                plain = key.split(":", 1)[-1] if ":" in key else key
                ltp = _safe_float(quote.get("last_price") if isinstance(quote, dict) else quote)
                result[original_sym] = ltp
                # also expose plain symbol for convenience
                if original_sym != plain:
                    result[plain] = ltp

        self._log.info("zerodha_adapter.get_ltp.ok", count=len(result))
        return result
