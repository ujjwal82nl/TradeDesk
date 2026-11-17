"""Holding Pydantic schemas for individual and merged (cross-broker) views."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class HoldingResponse(BaseModel):
    """Single holding record sourced from one broker account."""

    id: int
    broker_account_id: int
    broker_name: Optional[str] = None
    symbol: str
    exchange: str
    isin: Optional[str] = None
    quantity: float
    average_cost: float
    current_price: float
    current_value: float
    pnl: float
    pnl_percent: float
    day_change: float
    day_change_percent: float
    product_type: str = Field(..., description="E.g. 'CNC', 'NRML'.")
    instrument_type: str = Field(..., description="E.g. 'EQ', 'MF'.")
    supports_trade_lots: bool = False
    last_updated: datetime

    model_config = {"from_attributes": True}


class HoldingTradeLot(BaseModel):
    """Represents an individual open buy trade execution (tax lot) contributing to a holding."""

    trade_id: str
    order_id: str
    trade_date: str
    transaction_type: str = "BUY"
    quantity: float
    original_quantity: float
    price: float
    amount: float
    current_price: float
    current_value: float
    pnl: float
    pnl_percent: float
    holding_days: int
    exchange: str = "NSE"
    is_opening_lot: bool = False
    notes: Optional[str] = None


class HoldingLotsResponse(BaseModel):
    """Full trade lots breakdown for an equity holding."""

    holding_id: Optional[int] = None
    symbol: str
    isin: Optional[str] = None
    broker_name: str
    broker_account_id: int
    total_quantity: float
    average_cost: float
    current_price: float
    current_value: float
    total_pnl: float
    total_pnl_percent: float
    supports_historical_trades: bool = True
    unmatched_quantity: float = 0.0
    lots: List[HoldingTradeLot] = Field(default_factory=list)
    message: Optional[str] = None


class BrokerHoldingBreakdown(BaseModel):
    """Breakdown of one stock's position held with a specific broker."""

    holding_id: Optional[int] = None
    broker_name: str
    quantity: float
    average_cost: float
    value: float
    pnl: float
    supports_trade_lots: bool = False


class MergedHoldingResponse(BaseModel):
    """Aggregated cross-broker view of a single stock/instrument."""

    symbol: str
    isin: Optional[str] = None
    total_quantity: float
    weighted_avg_cost: float = Field(
        ..., description="Quantity-weighted average cost across all brokers."
    )
    current_price: float
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    brokers: List[BrokerHoldingBreakdown] = Field(
        default_factory=list,
        description="Per-broker breakdown for this holding.",
    )
