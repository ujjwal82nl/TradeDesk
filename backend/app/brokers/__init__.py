"""
brokers package – broker abstraction layer for the Antigravity dashboard.

Public surface:
    BaseBroker          – abstract base class every adapter implements
    BrokerFactory       – creates adapter instances from config
    PortfolioAggregator – merges data from multiple brokers
    Data models         – HoldingData, PositionData, OrderData, etc.
"""

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
from app.brokers.aggregator import PortfolioAggregator
from app.brokers.factory import BrokerFactory

__all__ = [
    "BaseBroker",
    "BrokerFactory",
    "PortfolioAggregator",
    "HoldingData",
    "PositionData",
    "OrderData",
    "TradeData",
    "FundsData",
    "PlaceOrderRequest",
    "ModifyOrderRequest",
]
