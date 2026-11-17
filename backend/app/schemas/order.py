"""Order placement, modification and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PlaceOrderRequest(BaseModel):
    """Payload for submitting a new order through any connected broker."""

    symbol: str = Field(..., description="Trading symbol, e.g. 'RELIANCE'.")
    exchange: str = Field(..., description="Exchange segment, e.g. 'NSE', 'BSE', 'NFO'.")
    transaction_type: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]
    product_type: str = Field(..., description="E.g. 'CNC', 'MIS', 'NRML'.")
    quantity: int = Field(..., ge=1)
    price: Optional[float] = Field(
        default=None, description="Limit price (required for LIMIT and SL orders)."
    )
    trigger_price: Optional[float] = Field(
        default=None, description="Trigger price (required for SL and SL-M orders)."
    )
    broker_account_id: int = Field(
        ..., description="Target broker account to route the order through."
    )
    tag: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Algo/strategy tag for order attribution.",
    )


class ModifyOrderRequest(BaseModel):
    """Partial update payload for an open/pending order."""

    quantity: Optional[int] = Field(default=None, ge=1)
    price: Optional[float] = Field(default=None)
    trigger_price: Optional[float] = Field(default=None)
    order_type: Optional[str] = Field(default=None)


class OrderResponse(BaseModel):
    """Serialised order record returned from the API."""

    id: int
    broker_account_id: Optional[int] = None
    broker_order_id: str = Field(
        ..., description="Order ID assigned by the broker."
    )
    broker_name: Optional[str] = "DHAN"
    symbol: str
    exchange: str
    transaction_type: str
    order_type: str
    product_type: str
    quantity: int
    filled_quantity: int
    pending_quantity: int
    price: Optional[float] = None
    average_price: Optional[float] = None
    status: str = Field(
        ...,
        description="E.g. 'OPEN', 'COMPLETE', 'CANCELLED', 'REJECTED'.",
    )
    order_timestamp: datetime
    remarks: Optional[str] = None

    model_config = {"from_attributes": True}
