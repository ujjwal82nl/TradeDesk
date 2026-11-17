"""Options strategy builder Pydantic schemas."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Strategy creation
# ---------------------------------------------------------------------------


class StrategyLegCreate(BaseModel):
    """One leg (instrument) within a multi-leg options strategy."""

    symbol: str
    transaction_type: str = Field(..., description="'BUY' or 'SELL'.")
    quantity: int = Field(..., ge=1)
    strike_price: float
    option_type: str = Field(..., description="'CE' or 'PE'.")
    expiry_date: date
    entry_price: float = Field(..., description="Premium paid/received per unit.")


class StrategyCreate(BaseModel):
    """Payload for recording a new options strategy."""

    name: str = Field(..., min_length=1, description="User-defined strategy name.")
    strategy_type: str = Field(
        ...,
        description="E.g. 'IRON_CONDOR', 'BULL_CALL_SPREAD', 'STRADDLE'.",
    )
    underlying: str = Field(..., description="Underlying symbol, e.g. 'NIFTY'.")
    expiry_date: date
    broker_account_id: int


# ---------------------------------------------------------------------------
# Strategy responses
# ---------------------------------------------------------------------------


class StrategyLegResponse(BaseModel):
    """Serialised strategy leg with current market data."""

    symbol: str
    transaction_type: str
    quantity: int
    strike_price: float
    option_type: str
    expiry_date: date
    entry_price: float
    current_price: float
    pnl: float

    model_config = {"from_attributes": True}


class StrategyResponse(BaseModel):
    """Full strategy record with payoff metrics and live P&L."""

    id: int
    name: str
    strategy_type: str
    underlying: str
    expiry_date: date
    status: str = Field(..., description="'ACTIVE', 'EXPIRED', 'CLOSED'.")
    max_profit: Optional[float] = Field(
        default=None, description="Maximum theoretical profit."
    )
    max_loss: Optional[float] = Field(
        default=None, description="Maximum theoretical loss."
    )
    breakeven_lower: Optional[float] = Field(
        default=None, description="Lower breakeven price of the underlying."
    )
    breakeven_upper: Optional[float] = Field(
        default=None, description="Upper breakeven price of the underlying."
    )
    net_premium: float = Field(
        ..., description="Net premium collected (positive) or paid (negative)."
    )
    margin_used: float
    current_pnl: float
    days_to_expiry: int
    probability_of_profit: Optional[float] = Field(
        default=None, description="Statistical PoP (0-1) based on implied volatility."
    )
    legs: List[StrategyLegResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
