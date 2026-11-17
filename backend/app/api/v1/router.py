"""
Main API v1 router.

Aggregates all sub-routers and mounts them under their canonical prefixes.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    algo,
    alerts,
    analytics,
    auth,
    brokers,
    dividends,
    holdings,
    margin,
    orders,
    portfolio,
    positions,
    strategies,
    trades,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
api_router.include_router(holdings.router, prefix="/holdings", tags=["Holdings"])
api_router.include_router(positions.router, prefix="/positions", tags=["Positions"])
api_router.include_router(orders.router, prefix="/orders", tags=["Orders"])
api_router.include_router(trades.router, prefix="/trades", tags=["Trades"])
api_router.include_router(dividends.router, prefix="/dividends", tags=["Dividends"])
api_router.include_router(margin.router, prefix="/margin", tags=["Margin"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
api_router.include_router(algo.router, prefix="/algo", tags=["Algo Engine"])
api_router.include_router(brokers.router, prefix="/brokers", tags=["Brokers"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts & Telegram"])
