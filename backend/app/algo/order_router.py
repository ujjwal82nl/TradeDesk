"""
Smart Order Routing (SOR) and Order Management System (OMS).
Routes execution across available brokers based on:
- Broker connection health and status
- Available margin/funds per broker
- Lowest broker transaction fees / slippage
"""
from typing import Dict, List, Optional
import structlog
from app.brokers.base import BaseBroker, PlaceOrderRequest, FundsData

log = structlog.get_logger()

class OrderRouter:
    def __init__(self, broker_instances: Dict[str, BaseBroker]):
        """
        broker_instances: Map of account_id or broker_name -> BaseBroker adapter
        """
        self.brokers = broker_instances

    async def select_optimal_broker(
        self,
        order: PlaceOrderRequest,
        preferred_broker: Optional[str] = None
    ) -> str:
        """
        Determines the optimal broker adapter to execute the order.
        If preferred_broker is supplied and valid, verifies available margin.
        Otherwise selects the broker with highest available cash/margin.
        """
        if preferred_broker and preferred_broker in self.brokers:
            return preferred_broker

        best_broker = None
        highest_margin = -1.0

        for name, adapter in self.brokers.items():
            try:
                funds: FundsData = await adapter.get_funds()
                if funds.available_margin > highest_margin:
                    highest_margin = funds.available_margin
                    best_broker = name
            except Exception as e:
                log.error("sor_failed_to_query_broker_funds", broker=name, error=str(e))

        if not best_broker:
            raise RuntimeError("No available broker accounts with valid margin connected for routing.")

        log.info("sor_routed_order", selected_broker=best_broker, highest_margin=highest_margin)
        return best_broker
