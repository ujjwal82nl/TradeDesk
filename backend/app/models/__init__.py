"""Models package — re-exports all ORM models and enums.

Import from this package to ensure all mapper configurations are registered
before ``Base.metadata.create_all()`` or Alembic migrations are invoked.
"""

from app.models.algo import AlgoMode, AlgoRun, AlgoStatus, AlgoStrategy, SignalType, TradeSignal
from app.models.alert import AlertNotification, AlertRule, SignalState
from app.models.broker import BrokerAccount, BrokerName, BrokerProvider
from app.models.dividend import Dividend
from app.models.holding import BrokerTradeHistory, Holding, HoldingLot
from app.models.margin import MarginSnapshot
from app.models.order import Order, OrderStatus, OrderType, TransactionType
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.strategy import OptionStrategy, StrategyLeg, StrategyStatus, StrategyType
from app.models.trade import Trade
from app.models.user import User

__all__ = [
    # user
    "User",
    # broker
    "BrokerName",
    "BrokerProvider",
    "BrokerAccount",
    # holding
    "Holding",
    "HoldingLot",
    "BrokerTradeHistory",
    # position
    "Position",
    # order
    "TransactionType",
    "OrderType",
    "OrderStatus",
    "Order",
    # trade
    "Trade",
    # dividend
    "Dividend",
    # margin
    "MarginSnapshot",
    # portfolio
    "PortfolioSnapshot",
    # strategy
    "StrategyType",
    "StrategyStatus",
    "OptionStrategy",
    "StrategyLeg",
    # algo
    "AlgoStatus",
    "AlgoMode",
    "AlgoRun",
    "AlgoStrategy",
    "SignalType",
    "TradeSignal",
    # alert
    "AlertRule",
    "AlertNotification",
    "SignalState",
]
