"""
base.py – Abstract broker interface and shared Pydantic data models.

Every broker adapter must inherit from ``BaseBroker`` and implement all
abstract async methods.  The Pydantic models defined here form the
canonical internal representation used throughout the platform; adapters
are responsible for translating broker-specific payloads into these
models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Canonical data models
# ---------------------------------------------------------------------------


class HoldingData(BaseModel):
    """Represents a long-term equity / mutual-fund holding."""

    symbol: str = Field(..., description="Trading symbol (e.g. RELIANCE)")
    exchange: str = Field(..., description="Exchange code (e.g. NSE, BSE)")
    isin: str = Field(..., description="12-character ISIN")
    quantity: float = Field(..., description="Total held quantity")
    average_cost: float = Field(..., description="Average acquisition cost per share")
    current_price: float = Field(..., description="Last traded price")
    current_value: float = Field(..., description="current_price × quantity")
    pnl: float = Field(..., description="Unrealised profit/loss in absolute terms")
    pnl_percent: float = Field(..., description="Unrealised P&L as a percentage")
    day_change: float = Field(..., description="Intra-day price change")
    day_change_percent: float = Field(..., description="Intra-day price change %")
    product_type: str = Field(..., description="Product type (e.g. CNC, DELIVERY)")
    instrument_type: str = Field(..., description="EQ, ETF, MF, etc.")


class PositionData(BaseModel):
    """Represents an intra-day or carry-forward open position."""

    symbol: str
    exchange: str
    product_type: str
    quantity: float = Field(..., description="Net quantity (positive = long, negative = short)")
    buy_qty: float = Field(default=0.0)
    sell_qty: float = Field(default=0.0)
    average_price: float
    last_price: float
    pnl: float
    day_pnl: float
    multiplier: float = Field(default=1.0, description="Lot/contract multiplier")
    instrument_type: str = Field(default="FUT", description="EQ, FUT, OPT, etc.")
    expiry_date: Optional[datetime] = None
    strike_price: Optional[float] = None
    option_type: Optional[str] = Field(
        default=None, description="CE or PE for options"
    )
    lot_size: int = Field(default=1)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None


class OrderData(BaseModel):
    """Represents a single order (open, executed, cancelled, or rejected)."""

    broker_order_id: str
    symbol: str
    exchange: str
    transaction_type: str = Field(..., description="BUY or SELL")
    order_type: str = Field(..., description="LIMIT, MARKET, SL, SL-M")
    product_type: str
    quantity: float
    filled_qty: float = Field(default=0.0)
    price: float
    trigger_price: float = Field(default=0.0)
    average_price: float = Field(default=0.0)
    status: str = Field(
        ..., description="PENDING, OPEN, COMPLETE, CANCELLED, REJECTED"
    )
    timestamp: datetime
    remarks: str = Field(default="")


class TradeData(BaseModel):
    """Represents an executed trade (fill)."""

    broker_trade_id: str
    broker_order_id: str
    symbol: str
    exchange: str
    transaction_type: str = Field(..., description="BUY or SELL")
    quantity: float
    price: float
    trade_value: float = Field(..., description="quantity × price")
    timestamp: datetime


class FundsData(BaseModel):
    """Represents the account's margin / cash summary."""

    available_margin: float
    used_margin: float
    span_margin: float
    exposure_margin: float
    collateral: float
    cash_balance: float
    total_balance: float


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class PlaceOrderRequest(BaseModel):
    """Payload for placing a new order."""

    symbol: str
    exchange: str
    transaction_type: str = Field(..., description="BUY or SELL")
    order_type: str = Field(..., description="LIMIT, MARKET, SL, SL-M")
    product_type: str
    quantity: int
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    tag: Optional[str] = Field(default=None, description="Arbitrary client-side tag")


class ModifyOrderRequest(BaseModel):
    """Payload for modifying an existing open order.

    All fields are optional; only provided fields will be updated.
    """

    quantity: Optional[int] = None
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    order_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Abstract broker base class
# ---------------------------------------------------------------------------


class BaseBroker(ABC):
    """Abstract base class that every broker adapter must implement.

    All methods are *async* to allow non-blocking I/O for concurrent
    multi-broker aggregation.  Implementations MUST NOT perform blocking
    network calls on the event loop; use ``asyncio.to_thread`` or an
    async HTTP client.
    """

    # ------------------------------------------------------------------
    # Optional / Extended Capabilities
    # ------------------------------------------------------------------

    # Feature flag: True if the broker supports historical trade logs
    supports_historical_trades: bool = False

    async def get_historical_trades(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
    ) -> List[dict]:
        """Fetch historical trades for tax lot reconstruction.
        
        Returns empty list if unsupported by the broker.
        """
        return []

    # ------------------------------------------------------------------
    # Portfolio data
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_holdings(self) -> List[HoldingData]:
        """Return all long-term holdings in the demat account."""

    @abstractmethod
    async def get_positions(self) -> List[PositionData]:
        """Return all current intra-day and carry-forward open positions."""

    @abstractmethod
    async def get_orders(self) -> List[OrderData]:
        """Return the order book for the current trading session."""

    @abstractmethod
    async def get_trades(self) -> List[TradeData]:
        """Return the trade book (fills) for the current trading session."""

    @abstractmethod
    async def get_funds(self) -> FundsData:
        """Return margin / funds summary for the account."""

    async def get_margin(self) -> Dict[str, Any]:
        """Return margin / funds as a dictionary for margin service compatibility."""
        funds = await self.get_funds()
        return funds.model_dump()

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    @abstractmethod
    async def place_order(self, order: PlaceOrderRequest) -> str:
        """Place a new order and return the broker-assigned order ID."""

    @abstractmethod
    async def modify_order(self, order_id: str, modifications: ModifyOrderRequest) -> bool:
        """Modify an existing open order.  Returns ``True`` on success."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing open order.  Returns ``True`` on success."""

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """Return the last traded price for each requested symbol.

        Args:
            symbols: List of symbol strings in a format agreed by each
                     adapter (e.g. ``"NSE:RELIANCE"`` for Zerodha or
                     plain ``"RELIANCE"`` for Dhan).

        Returns:
            Mapping of ``symbol -> ltp``.
        """
