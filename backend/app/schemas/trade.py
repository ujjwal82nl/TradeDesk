"""Trade history and trade journal Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TradeResponse(BaseModel):
    """Executed trade record (fills) from a broker account."""

    id: int
    broker_account_id: Optional[int] = None
    broker_name: Optional[str] = "DHAN"
    symbol: str
    exchange: str
    transaction_type: str = Field(..., description="'BUY' or 'SELL'.")
    quantity: float
    price: float
    trade_value: float = Field(..., description="quantity × price.")
    product_type: str
    trade_timestamp: datetime
    journal_entry: Optional[str] = Field(
        default=None,
        description="User-authored trade rationale or reflection.",
    )
    notes: Optional[str] = Field(
        default=None, description="Free-form supplementary notes."
    )

    model_config = {"from_attributes": True}


class JournalUpdateRequest(BaseModel):
    """Payload for adding or editing a trade journal entry."""

    journal_entry: str = Field(
        ..., min_length=1, description="Trade rationale, analysis, or post-trade review."
    )
    notes: Optional[str] = Field(
        default=None, description="Optional supplementary notes."
    )
