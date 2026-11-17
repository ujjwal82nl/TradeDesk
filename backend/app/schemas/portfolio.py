"""Portfolio summary and snapshot Pydantic schemas."""

from __future__ import annotations

import datetime as dt
from typing import List

from pydantic import BaseModel, Field


class PortfolioSummary(BaseModel):
    """Aggregated portfolio metrics across all connected broker accounts."""

    total_net_worth: float = Field(
        ..., description="Cash + portfolio value across all brokers."
    )
    total_portfolio_value: float = Field(
        ..., description="Market value of all open holdings and positions."
    )
    today_pnl: float = Field(..., description="Intraday profit/loss (absolute).")
    today_pnl_percent: float = Field(
        ..., description="Intraday profit/loss as percentage of previous close value."
    )
    unrealized_pnl: float = Field(
        ..., description="Total open position P&L (MTM)."
    )
    realized_pnl: float = Field(
        ..., description="Booked profit/loss for the current financial year."
    )
    total_cash: float = Field(..., description="Sum of available cash across all brokers.")
    total_margin_used: float = Field(
        ..., description="Aggregate margin utilised across all broker accounts."
    )
    broker_count: int = Field(..., description="Number of active broker accounts.")
    last_updated: dt.datetime = Field(
        ..., description="Timestamp of the most recent data sync."
    )


class BrokerAllocation(BaseModel):
    """Portfolio exposure breakdown for a single broker."""

    broker_name: str
    value: float = Field(..., description="Market value of holdings with this broker.")
    percentage: float = Field(..., description="Share of total portfolio value (0-100).")
    cash: float = Field(..., description="Available cash with this broker.")


class AssetAllocation(BaseModel):
    """Portfolio exposure breakdown by asset/instrument type."""

    asset_type: str = Field(
        ..., description="E.g. 'EQ', 'FUT', 'OPT', 'MF', 'BOND'."
    )
    value: float
    percentage: float = Field(..., description="Share of total portfolio value (0-100).")


class PortfolioSnapshotResponse(BaseModel):
    """Historical end-of-day portfolio snapshot for trend charts."""

    date: dt.date = Field(..., validation_alias="snapshot_date")
    total_net_worth: float
    total_portfolio_value: float
    today_pnl: float

    model_config = {"from_attributes": True, "populate_by_name": True}
