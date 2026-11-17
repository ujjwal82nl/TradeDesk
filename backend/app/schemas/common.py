"""Shared/common Pydantic schemas used across the trading platform."""

from __future__ import annotations

from datetime import date
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed).")
    page_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of items per page (max 500).",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic wrapper for paginated API responses."""

    items: List[T]
    total: int = Field(..., description="Total number of matching records.")
    page: int = Field(..., description="Current page number.")
    page_size: int = Field(..., description="Items per page.")

    @property
    def total_pages(self) -> int:
        """Compute total page count."""
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class DateRangeParams(BaseModel):
    """Optional date-range filter for time-series endpoints."""

    date_from: Optional[date] = Field(
        default=None, description="Inclusive start date (ISO 8601)."
    )
    date_to: Optional[date] = Field(
        default=None, description="Inclusive end date (ISO 8601)."
    )
