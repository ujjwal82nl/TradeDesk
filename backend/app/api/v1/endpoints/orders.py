"""
Orders endpoints.

Supports listing, placing, modifying, and cancelling orders
across connected broker accounts.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.order import (
    ModifyOrderRequest,
    OrderResponse,
    PlaceOrderRequest,
)
from app.services.orders_service import OrdersService

router = APIRouter()


class SyncOrdersResponse(BaseModel):
    """Result of an orders sync operation."""

    synced_at: str
    total_orders_synced: int = 0
    broker_results: dict = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[OrderResponse],
    summary="List orders with filters",
)
async def list_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    broker_account_id: Optional[int] = Query(None, description="Filter by broker account"),
    status: Optional[str] = Query(None, description="OPEN, COMPLETE, CANCELLED, REJECTED"),
    limit: int = Query(50, ge=1, le=200),
) -> List[OrderResponse]:
    """Return orders for the current user."""
    service = OrdersService(db, current_user.id)
    return await service.get_orders(
        broker_account_id=broker_account_id,
        status=status,
        limit=limit,
    )


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place a new order",
)
async def place_order(
    payload: PlaceOrderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    """Submit an order to the broker API and persist it locally."""
    service = OrdersService(db, current_user.id)
    try:
        return await service.place_order(
            broker_account_id=payload.broker_account_id,
            payload=payload,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order placement failed: {exc}",
        )


@router.put(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Modify an open order",
)
async def modify_order(
    order_id: Annotated[int, Path(ge=1)],
    payload: ModifyOrderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    """Modify price or quantity on an open order."""
    service = OrdersService(db, current_user.id)
    try:
        return await service.modify_order(order_id=order_id, payload=payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order modification failed: {exc}",
        )


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel an open order",
)
async def cancel_order(
    order_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Cancel an open order at the broker."""
    service = OrdersService(db, current_user.id)
    try:
        success = await service.cancel_order(order_id=order_id)
        return {"success": success, "order_id": order_id}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order cancellation failed: {exc}",
        )


@router.post(
    "/sync",
    response_model=SyncOrdersResponse,
    summary="Sync orders from all brokers",
)
async def sync_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyncOrdersResponse:
    """Pull the latest order status from all connected broker accounts."""
    from datetime import datetime, timezone

    service = OrdersService(db, current_user.id)
    orders = await service.sync_orders()
    return SyncOrdersResponse(
        synced_at=datetime.now(timezone.utc).isoformat(),
        total_orders_synced=len(orders),
    )
