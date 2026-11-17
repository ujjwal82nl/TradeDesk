"""Margin utilisation Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MarginResponse(BaseModel):
    """Current margin snapshot for a single broker account."""

    broker_name: str
    broker_account_id: Optional[int] = None
    available_margin: float = Field(
        ..., description="Margin immediately available for new positions."
    )
    used_margin: float = Field(
        ..., description="Total margin locked for open positions."
    )
    span_margin: float = Field(
        ..., description="SPAN margin component (futures/options)."
    )
    exposure_margin: float = Field(
        ..., description="Exposure margin component."
    )
    collateral: float = Field(
        ..., description="Value of pledged securities accepted as margin."
    )
    cash_balance: float = Field(
        ..., description="Uninvested cash balance."
    )
    total_balance: float = Field(
        ..., description="cash_balance + collateral (effective total margin)."
    )
    timestamp: datetime

    model_config = {"from_attributes": True}


class MarginSummary(BaseModel):
    """Aggregated margin view across all broker accounts."""

    total_available: float
    total_used: float
    total_collateral: float
    total_cash: float
    utilization_percent: float = Field(
        ..., description="total_used / (total_available + total_used) × 100."
    )
    brokers: List[MarginResponse] = Field(
        default_factory=list,
        description="Per-broker margin details.",
    )
