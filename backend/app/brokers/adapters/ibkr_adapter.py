"""
ibkr_adapter.py – Interactive Brokers (IBKR) broker adapter (stub).

IMPORTANT: Interactive Brokers requires either:
  - **IB Gateway** (headless) running locally, OR
  - **Trader Workstation (TWS)** desktop application running and logged in

before any programmatic connection is possible.  The native IB API uses
a proprietary binary socket protocol (TWS API / EClientSocket).  Two
popular Python wrappers exist:
  - ``ibapi`` (official IBKR package)  https://interactivebrokers.github.io/tws-api/
  - ``ib_insync``                       https://ib-insync.readthedocs.io/

This stub provides the complete interface skeleton so the rest of the
platform can reference ``IBKRAdapter`` without errors.  Replace the
``NotImplementedError`` bodies with real ``ib_insync`` calls once the
TWS / IB Gateway connection is configured.

Recommended integration approach:
    1. Install: ``pip install ib_insync``
    2. Start IB Gateway on host:port (default 127.0.0.1:4002 for paper)
    3. Replace each ``raise NotImplementedError(...)`` with the
       corresponding ``ib_insync`` request (``ib.portfolio()``, etc.)
    4. Wrap synchronous ib_insync calls with ``asyncio.to_thread``.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from app.brokers.base import (
    BaseBroker,
    FundsData,
    HoldingData,
    ModifyOrderRequest,
    OrderData,
    PlaceOrderRequest,
    PositionData,
    TradeData,
)

logger = logging.getLogger(__name__)

_NOT_IMPLEMENTED_MSG = (
    "IBKR adapter requires IB Gateway or TWS running – integration pending. "
    "See module docstring for setup instructions."
)


class IBKRAdapter(BaseBroker):
    """Stub broker adapter for Interactive Brokers.

    Connects to IB Gateway or Trader Workstation via the TWS API.

    Args:
        host: Hostname or IP address where IB Gateway / TWS is running.
              Typically ``"127.0.0.1"`` for local installations.
        port: Port number. Defaults:
              - Live trading via IB Gateway: ``4001``
              - Paper trading via IB Gateway: ``4002``
              - Live trading via TWS:        ``7496``
              - Paper trading via TWS:       ``7497``
        client_id: Unique integer client ID (0–31).  Multiple simultaneous
                   connections to the same TWS/Gateway must use distinct IDs.

    Example::

        adapter = IBKRAdapter(host="127.0.0.1", port=4002, client_id=1)
        # All methods raise NotImplementedError until fully implemented.
    """

    def __init__(self, host: str, port: int, client_id: int) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        # Future: self._ib = IB(); self._ib.connect(host, port, clientId=client_id)
        logger.info(
            "IBKRAdapter initialised (stub) – host=%s port=%d client_id=%d",
            host, port, client_id,
        )

    # ------------------------------------------------------------------
    # Connection lifecycle (future work)
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish connection to IB Gateway / TWS.

        Future implementation::

            from ib_insync import IB
            self._ib = IB()
            await self._ib.connectAsync(self.host, self.port, clientId=self.client_id)
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    async def disconnect(self) -> None:
        """Gracefully disconnect from IB Gateway / TWS.

        Future implementation::

            self._ib.disconnect()
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    # ------------------------------------------------------------------
    # Portfolio data
    # ------------------------------------------------------------------

    async def get_holdings(self) -> List[HoldingData]:
        """Return all IBKR portfolio positions as holdings.

        Future implementation uses ``ib.portfolio()`` which returns
        ``PortfolioItem`` objects with contract + position details.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    async def get_positions(self) -> List[PositionData]:
        """Return all open positions.

        Future implementation uses ``ib.positions()`` which returns
        ``Position`` namedtuples.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    async def get_orders(self) -> List[OrderData]:
        """Return all open and recently filled orders.

        Future implementation uses ``ib.openOrders()`` and
        ``ib.completedOrders()``.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    async def get_trades(self) -> List[TradeData]:
        """Return all executions (fills) for the current session.

        Future implementation uses ``ib.executions()``.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    async def get_funds(self) -> FundsData:
        """Return account summary / margin information.

        Future implementation uses ``ib.accountSummary()`` querying tags
        such as ``NetLiquidation``, ``AvailableFunds``, ``MaintMarginReq``.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    async def place_order(self, order: PlaceOrderRequest) -> str:
        """Place an order via TWS API.

        Future implementation constructs an ``ib_insync.Stock`` (or
        ``Future``/``Option``) contract and a ``LimitOrder`` /
        ``MarketOrder`` object, then calls ``ib.placeOrder(contract, order)``.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    async def modify_order(self, order_id: str, modifications: ModifyOrderRequest) -> bool:
        """Modify an existing open order.

        In TWS API, modification is done by re-submitting the same
        ``orderId`` with updated fields via ``ib.placeOrder()``.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing open order.

        Future implementation uses ``ib.cancelOrder(trade)`` where
        ``trade`` is located by matching ``order_id`` in ``ib.trades()``.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """Return last traded prices for the given symbols.

        Future implementation requests snapshot market data via
        ``ib.reqMktData(contract, snapshot=True)`` and reads
        ``ticker.last`` or ``ticker.close``.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
