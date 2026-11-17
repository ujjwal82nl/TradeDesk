"""Dividend income tracking Pydantic schemas."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class DividendResponse(BaseModel):
    """Individual dividend credit record."""

    id: int
    broker_name: str
    broker_account_id: Optional[int] = None
    symbol: str
    company_name: Optional[str] = None
    isin: Optional[str] = None
    ex_date: Optional[date] = Field(default=None, description="Ex-dividend date.")
    payment_date: Optional[date] = Field(
        default=None, description="Actual credit/payment date."
    )
    dividend_per_share: float = 0.0
    quantity: float = Field(default=0.0, description="Shares held on the record date.")
    total_dividend: float = Field(
        default=0.0, description="dividend_per_share × quantity (gross)."
    )
    tax_deducted: float = Field(default=0.0, description="Withholding tax (TDS).")
    net_dividend: float = Field(
        ..., description="After applicable withholding tax deductions."
    )

    model_config = {"from_attributes": True}


class CreateDividendRequest(BaseModel):
    """Payload to manually record a received dividend payout."""

    broker_account_id: int
    symbol: str
    company_name: Optional[str] = None
    isin: Optional[str] = None
    ex_date: Optional[date] = None
    payment_date: Optional[date] = None
    dividend_per_share: float = 0.0
    quantity: float = 0.0
    total_dividend: Optional[float] = None
    tax_deducted: float = 0.0
    net_dividend: Optional[float] = None


class MonthlyIncome(BaseModel):
    """Aggregated dividend income for a calendar month."""

    year: int
    month: int = Field(..., ge=1, le=12)
    month_name: str = Field(..., description="Full month name, e.g. 'January'.")
    total_income: float = Field(..., description="Sum of net dividends for the month.")
    dividend_count: int = Field(
        ..., description="Number of individual dividend credits."
    )


class StockDividendSummary(BaseModel):
    """Lifetime dividend summary for a single stock/symbol."""

    symbol: str
    company_name: Optional[str] = None
    total_received: float = Field(
        ..., description="Cumulative net dividend received."
    )
    yield_on_cost: Optional[float] = Field(
        default=None,
        description="Annualised yield on average cost (percentage).",
    )
    last_dividend_date: Optional[date] = Field(
        default=None, description="Most recent ex-dividend date recorded."
    )
    quantity: Optional[float] = Field(
        default=0.0, description="Quantity held currently / on record date."
    )
