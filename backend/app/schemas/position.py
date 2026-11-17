"""Position Pydantic schemas including options greeks."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class PositionResponse(BaseModel):
    """Open trading position from a broker account."""

    id: int
    broker_account_id: Optional[int] = None
    broker_name: Optional[str] = None
    symbol: str
    exchange: str
    product_type: str = Field(..., description="E.g. 'MIS', 'NRML', 'CNC'.")
    quantity: float = Field(..., description="Net quantity (positive=long, negative=short).")
    buy_quantity: float
    sell_quantity: float
    average_price: float
    last_price: float
    pnl: float
    day_pnl: float
    instrument_type: str = Field(..., description="E.g. 'EQ', 'FUT', 'OPT'.")
    expiry_date: Optional[date] = None
    strike_price: Optional[float] = None
    option_type: Optional[str] = Field(
        default=None, description="'CE' (Call) or 'PE' (Put)."
    )
    lot_size: int = Field(default=1)
    last_updated: datetime

    @computed_field
    @property
    def is_open(self) -> bool:
        """True if net quantity is non-zero (position is active)."""
        return self.quantity != 0

    @computed_field
    @property
    def status(self) -> str:
        """Position status: 'OPEN' if active, 'CLOSED' if squared off."""
        return "OPEN" if self.quantity != 0 else "CLOSED"

    model_config = {"from_attributes": True}


class OptionPositionResponse(PositionResponse):
    """Option position enriched with Black-Scholes greeks."""

    delta: Optional[float] = Field(
        default=None, description="Rate of change of option price w.r.t. underlying."
    )
    theta: Optional[float] = Field(
        default=None, description="Time decay per calendar day."
    )
    vega: Optional[float] = Field(
        default=None, description="Sensitivity to 1% change in implied volatility."
    )
    gamma: Optional[float] = Field(
        default=None, description="Rate of change of delta w.r.t. underlying."
    )


class GreeksSummary(BaseModel):
    """Aggregated portfolio greeks across all open option positions."""

    net_delta: float
    net_theta: float
    net_vega: float
    net_gamma: float
    total_positions: int = Field(
        ..., description="Number of option positions included in the summary."
    )
