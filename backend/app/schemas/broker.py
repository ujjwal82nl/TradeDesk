"""Broker provider and account Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Broker provider
# ---------------------------------------------------------------------------


class BrokerProviderResponse(BaseModel):
    """Details of a supported broker integration (e.g. Dhan, Zerodha)."""

    id: int
    name: str = Field(..., description="Internal slug identifier, e.g. 'dhan'.")
    display_name: str = Field(..., description="Human-readable broker name.")
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Broker account
# ---------------------------------------------------------------------------


class BrokerAccountCreate(BaseModel):
    """Payload for linking a new broker trading account."""

    broker_id: int = Field(..., description="FK to BrokerProvider.id.")
    account_id: str = Field(..., description="Broker-assigned account/client ID.")
    account_name: str = Field(..., description="User-defined display name.")
    access_token: str = Field(..., description="OAuth / API access token.")
    refresh_token: Optional[str] = Field(
        default=None, description="OAuth refresh token (if applicable)."
    )


class BrokerAccountResponse(BaseModel):
    """Serialised broker account record (tokens intentionally excluded)."""

    id: int
    broker_id: int
    account_name: str
    account_id: str
    is_active: bool
    is_default: bool
    created_at: datetime
    token_expiry: Optional[datetime] = None
    is_token_expired: bool = False
    token_status: str = Field(
        default="ACTIVE",
        description="'ACTIVE', 'EXPIRED', 'INACTIVE', or 'ERROR'",
    )
    status_message: Optional[str] = None
    broker: Optional[BrokerProviderResponse] = None

    model_config = {"from_attributes": True}


class BrokerAccountUpdate(BaseModel):
    """Partial update payload for a broker account."""

    access_token: Optional[str] = Field(
        default=None, description="New access token to replace the stored one."
    )
    account_name: Optional[str] = Field(default=None)
    is_default: Optional[bool] = Field(
        default=None,
        description="Set True to mark this as the user's default trading account.",
    )
