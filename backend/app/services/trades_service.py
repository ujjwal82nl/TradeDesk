"""
TradesService: executed trade history and trade journal management.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import BrokerAccount
from app.models.trade import Trade
from app.schemas.trade import JournalUpdateRequest, TradeResponse
from app.services.broker_service import BrokerService

logger = logging.getLogger(__name__)


class TradesService:
    """Application-layer service for trade fills and the trade journal."""

    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self._db = db
        self._user_id = user_id
        self._broker_svc = BrokerService(db)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_trades(
        self,
        broker_account_id: Optional[int] = None,
        symbol: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[TradeResponse]:
        """
        Return trade fill records for the user.

        Args:
            broker_account_id: Restrict to a single broker account.
            symbol: Filter by trading symbol.
            limit: Maximum records to return.
            offset: Pagination offset.
        """
        stmt = (
            select(Trade)
            .join(BrokerAccount, Trade.broker_account_id == BrokerAccount.id)
            .where(BrokerAccount.user_id == self._user_id)
        )
        if broker_account_id is not None:
            stmt = stmt.where(Trade.broker_account_id == broker_account_id)
        if symbol:
            stmt = stmt.where(Trade.symbol == symbol.upper())

        stmt = stmt.order_by(Trade.trade_timestamp.desc()).limit(limit).offset(offset)
        result = await self._db.execute(stmt)
        return [TradeResponse.model_validate(t) for t in result.scalars().all()]

    async def get_trade(self, trade_id: int) -> TradeResponse:
        """
        Fetch a single trade by ID.

        Raises:
            ValueError: if the trade does not exist or belongs to another user.
        """
        trade = await self._get_user_trade(trade_id)
        return TradeResponse.model_validate(trade)

    # ------------------------------------------------------------------
    # Journal
    # ------------------------------------------------------------------

    async def update_journal(
        self, trade_id: int, payload: JournalUpdateRequest
    ) -> TradeResponse:
        """
        Add or update a journal entry on an existing trade.

        Raises:
            ValueError: if the trade does not exist or belongs to another user.
        """
        trade = await self._get_user_trade(trade_id)
        trade.journal_entry = payload.journal_entry
        trade.notes = payload.notes
        await self._db.commit()
        await self._db.refresh(trade)
        return TradeResponse.model_validate(trade)

    async def auto_create_journal_entry(self, trade_id: int) -> TradeResponse:
        """
        Generate a concise auto-journal entry from trade metadata.

        The generated text provides a baseline narrative that the user can
        later refine through update_journal().

        Format:
            ``{BUY|SELL} {qty}x {symbol} @ {price} via {product_type}``

        Raises:
            ValueError: if the trade does not exist or belongs to another user.
        """
        trade = await self._get_user_trade(trade_id)

        if trade.journal_entry:
            logger.info("Trade %s already has a journal entry; skipping auto-create.", trade_id)
            return TradeResponse.model_validate(trade)

        entry = (
            f"{trade.transaction_type} {trade.quantity}× {trade.symbol} "
            f"@ ₹{trade.price:,.2f} via {trade.product_type} "
            f"on {trade.exchange} "
            f"| Trade value: ₹{trade.trade_value:,.2f}"
        )
        trade.journal_entry = entry
        await self._db.commit()
        await self._db.refresh(trade)
        return TradeResponse.model_validate(trade)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_user_trade(self, trade_id: int) -> Trade:
        stmt = (
            select(Trade)
            .join(BrokerAccount, Trade.broker_account_id == BrokerAccount.id)
            .where(Trade.id == trade_id, BrokerAccount.user_id == self._user_id)
        )
        result = await self._db.execute(stmt)
        trade = result.scalar_one_or_none()
        if not trade:
            raise ValueError(f"Trade {trade_id} not found for user {self._user_id}.")
        return trade
