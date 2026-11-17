"""
adapters package – concrete broker adapter implementations.

Available adapters
------------------
DhanAdapter     – Dhan HQ (dhanhq library)
ZerodhaAdapter  – Zerodha Kite (kiteconnect library)
INDMoneyAdapter – INDMoney stub (no official API)
IBKRAdapter     – Interactive Brokers stub (TWS / IB Gateway required)
"""

from app.brokers.adapters.dhan_adapter import DhanAdapter
from app.brokers.adapters.ibkr_adapter import IBKRAdapter
from app.brokers.adapters.indmoney_adapter import INDMoneyAdapter
from app.brokers.adapters.zerodha_adapter import ZerodhaAdapter

__all__ = [
    "DhanAdapter",
    "ZerodhaAdapter",
    "INDMoneyAdapter",
    "IBKRAdapter",
]
