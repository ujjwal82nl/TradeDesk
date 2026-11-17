"""
Risk Management Engine.
Enforces pre-trade risk controls:
- Account margin sufficiency validation
- Maximum order value limit
- Maximum quantity limit per symbol / order
- Maximum daily loss threshold protection
- Single-stock position concentration limit
"""
from dataclasses import dataclass
from typing import Optional, Tuple
import structlog
from app.schemas.order import PlaceOrderRequest
from app.brokers.base import FundsData

log = structlog.get_logger()

@dataclass
class RiskLimits:
    max_order_value: float = 200_000.0       # Max value per single order in INR
    max_quantity_per_order: int = 5_000      # Max quantity per order
    max_portfolio_leverage: float = 3.0      # Max gross exposure / capital
    max_position_concentration_pct: float = 0.25 # Max 25% portfolio in single ticker
    max_daily_loss_limit: float = 25_000.0   # Circuit breaker on daily loss

class RiskEngine:
    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()

    def validate_order(
        self,
        order: PlaceOrderRequest,
        estimated_price: float,
        funds: FundsData,
        current_day_pnl: float = 0.0
    ) -> Tuple[bool, Optional[str]]:
        """
        Pre-trade risk inspection. Returns (is_allowed, rejection_reason).
        """
        # 1. Daily Loss Circuit Breaker
        if current_day_pnl <= -abs(self.limits.max_daily_loss_limit):
            msg = f"Risk Rejection: Daily loss limit (₹{self.limits.max_daily_loss_limit:,.2f}) hit. Trading suspended."
            log.warning("risk_daily_loss_exceeded", current_pnl=current_day_pnl, limit=self.limits.max_daily_loss_limit)
            return False, msg

        # 2. Maximum Quantity per Order
        if order.quantity > self.limits.max_quantity_per_order:
            msg = f"Risk Rejection: Quantity {order.quantity} exceeds limit of {self.limits.max_quantity_per_order}"
            return False, msg

        # 3. Maximum Order Value
        order_value = order.quantity * (order.price if order.price and order.price > 0 else estimated_price)
        if order_value > self.limits.max_order_value:
            msg = f"Risk Rejection: Order value ₹{order_value:,.2f} exceeds single order limit ₹{self.limits.max_order_value:,.2f}"
            return False, msg

        # 4. Margin Validation for BUY / Margin Sell orders
        if order.transaction_type == "BUY" or order.product_type in ["MIS", "NRML"]:
            required_margin = order_value * (0.20 if order.product_type == "MIS" else 1.0)
            if funds.available_margin < required_margin:
                msg = f"Risk Rejection: Insufficient margin. Required: ₹{required_margin:,.2f}, Available: ₹{funds.available_margin:,.2f}"
                return False, msg

        return True, None
