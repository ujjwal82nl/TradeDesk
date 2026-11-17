"""
Trading Platform - FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine, Base

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    import asyncio
    log.info("Starting Trading Platform API", env=settings.ENVIRONMENT)
    # Create tables on startup (use Alembic for production migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database tables initialized")

    # Ensure broker providers and configured accounts exist
    await init_default_broker_accounts()

    # Start background alert monitor worker (SuperTrend & Telegram signals)
    monitor_task = asyncio.create_task(alert_rules_background_worker())

    yield

    # Graceful shutdown
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    log.info("Shutting down Trading Platform API")
    await engine.dispose()


async def alert_rules_background_worker() -> None:
    """Periodically check active alert rules (every 60s) for indicator flips."""
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.services.alert_service import AlertService

    # Initial delay on boot
    await asyncio.sleep(10)
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await AlertService.evaluate_all_active_rules(session)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("alert_rules_worker_cycle_error", error=str(exc))
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break


async def init_default_broker_accounts() -> None:
    """Ensure broker providers and configured accounts exist on startup."""
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.broker import BrokerProvider, BrokerAccount, BrokerName
    from app.models.user import User

    try:
        async with AsyncSessionLocal() as session:
            # Query all existing providers without type-cast errors
            res = await session.execute(select(BrokerProvider))
            providers_map = {}
            for p in res.scalars().all():
                key = (p.name.value if hasattr(p.name, "value") else str(p.name)).upper()
                providers_map[key] = p

            for name_enum, display in [
                (BrokerName.DHAN, "Dhan"),
                (BrokerName.ZERODHA, "Zerodha"),
                (BrokerName.INDMONEY, "INDMoney"),
                (BrokerName.IBKR, "Interactive Brokers"),
            ]:
                key = (name_enum.value if hasattr(name_enum, "value") else str(name_enum)).upper()
                if key not in providers_map:
                    provider = BrokerProvider(name=name_enum, display_name=display, is_active=True)
                    session.add(provider)
                    await session.flush()
                    providers_map[key] = provider

            res_users = await session.execute(select(User).where(User.is_active.is_(True)))
            users = res_users.scalars().all()

            for user in users:
                if settings.ZERODHA_USER_ID and "ZERODHA" in providers_map:
                    z_prov = providers_map["ZERODHA"]
                    res_acc = await session.execute(
                        select(BrokerAccount).where(
                            BrokerAccount.user_id == user.id,
                            BrokerAccount.broker_id == z_prov.id,
                        )
                    )
                    acc = res_acc.scalar_one_or_none()
                    if not acc:
                        acc = BrokerAccount(
                            user_id=user.id,
                            broker_id=z_prov.id,
                            account_id=settings.ZERODHA_USER_ID,
                            account_name=f"Zerodha ({settings.ZERODHA_USER_ID})",
                            is_active=True,
                            is_default=False,
                        )
                        session.add(acc)
                        log.info("Initialized Zerodha account", user_id=user.id, account_id=settings.ZERODHA_USER_ID)
                    else:
                        acc.account_id = settings.ZERODHA_USER_ID
                        acc.is_active = True

            await session.commit()
    except Exception as exc:
        log.warning("Could not auto-initialize broker accounts on startup", error=str(exc))


def create_application() -> FastAPI:
    application = FastAPI(
        title="TradeDesk Multi-Broker Platform",
        description="Unified dashboard for holdings, positions, orders, and analytics across multiple brokers.",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Middlewares
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)

    # Routers
    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_application()
