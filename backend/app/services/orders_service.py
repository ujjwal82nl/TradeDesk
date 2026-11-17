"""
OrdersService: place, modify, cancel and query orders across broker accounts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import BrokerAccount
from app.models.order import Order
from app.schemas.order import ModifyOrderRequest, OrderResponse, PlaceOrderRequest
from app.services.broker_service import BrokerService

logger = logging.getLogger(__name__)


class OrdersService:
    """Application-layer service for order management."""

    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self._db = db
        self._user_id = user_id
        self._broker_svc = BrokerService(db)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_orders(
        self,
        broker_account_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[OrderResponse]:
        """
        Return persisted order records for the user.

        Args:
            broker_account_id: Restrict results to a specific broker account.
            status: Filter by order status string (e.g. 'OPEN', 'COMPLETE').
            limit: Maximum number of records to return.
        """
        stmt = (
            select(Order)
            .join(BrokerAccount, Order.broker_account_id == BrokerAccount.id)
            .where(BrokerAccount.user_id == self._user_id)
        )
        if broker_account_id is not None:
            stmt = stmt.where(Order.broker_account_id == broker_account_id)
        if status:
            stmt = stmt.where(Order.status == status.upper())

        stmt = stmt.order_by(Order.order_timestamp.desc()).limit(limit)
        result = await self._db.execute(stmt)
        return [OrderResponse.model_validate(o) for o in result.scalars().all()]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def place_order(self, payload: PlaceOrderRequest) -> OrderResponse:
        """
        Submit an order to the broker and persist the resulting record.

        Raises:
            ValueError: if the broker account does not belong to this user.
            RuntimeError: if the broker API rejects the order.
        """
        adapter = await self._broker_svc.get_broker_instance(
            payload.broker_account_id, self._user_id
        )
        order_payload = payload.model_dump(exclude={"broker_account_id"})
        broker_response: dict = await adapter.place_order(order_payload)

        if not broker_response.get("order_id"):
            raise RuntimeError(
                f"Broker rejected order: {broker_response.get('message', 'unknown error')}"
            )

        order = Order(
            broker_account_id=payload.broker_account_id,
            broker_order_id=str(broker_response["order_id"]),
            symbol=payload.symbol,
            exchange=payload.exchange,
            transaction_type=payload.transaction_type,
            order_type=payload.order_type,
            product_type=payload.product_type,
            quantity=payload.quantity,
            filled_quantity=0,
            pending_quantity=payload.quantity,
            price=payload.price,
            average_price=None,
            status=broker_response.get("order_status", "OPEN"),
            order_timestamp=datetime.utcnow(),
            remarks=None,
        )
        self._db.add(order)
        await self._db.commit()
        await self._db.refresh(order)
        return OrderResponse.model_validate(order)

    async def modify_order(
        self,
        order_id: int,
        payload: ModifyOrderRequest,
    ) -> OrderResponse:
        """
        Modify a pending order via the broker API and update the DB record.

        Raises:
            ValueError: if the order is not found or does not belong to this user.
        """
        order = await self._get_user_order(order_id)
        adapter = await self._broker_svc.get_broker_instance(
            order.broker_account_id, self._user_id
        )

        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        await adapter.modify_order(order.broker_order_id, update_data)

        for field, value in update_data.items():
            setattr(order, field, value)

        await self._db.commit()
        await self._db.refresh(order)
        return OrderResponse.model_validate(order)

    async def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an open order via the broker API and mark it as CANCELLED in DB.

        Returns:
            True if the broker confirmed cancellation.

        Raises:
            ValueError: if the order is not found or does not belong to this user.
        """
        order = await self._get_user_order(order_id)
        adapter = await self._broker_svc.get_broker_instance(
            order.broker_account_id, self._user_id
        )

        success: bool = await adapter.cancel_order(order.broker_order_id)
        if success:
            order.status = "CANCELLED"
            await self._db.commit()
        return success

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_user_order(self, order_id: int) -> Order:
        stmt = (
            select(Order)
            .join(BrokerAccount, Order.broker_account_id == BrokerAccount.id)
            .where(Order.id == order_id, BrokerAccount.user_id == self._user_id)
        )
        result = await self._db.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found for user {self._user_id}.")
        return order
