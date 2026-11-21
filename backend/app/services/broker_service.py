"""
BrokerService: manage broker provider catalogue and user account connections.

The service also acts as an adapter factory — get_broker_instance() returns a
protocol-compliant broker adapter that abstracts Dhan, Zerodha, etc.
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import BrokerAccount, BrokerProvider
from app.schemas.broker import BrokerAccountCreate, BrokerAccountUpdate


# ---------------------------------------------------------------------------
# Broker adapter protocol
# ---------------------------------------------------------------------------


class BrokerAdapter(Protocol):
    """Structural interface that all broker adapters must satisfy."""

    async def get_holdings(self) -> list[dict[str, Any]]: ...
    async def get_positions(self) -> list[dict[str, Any]]: ...
    async def get_orders(self) -> list[dict[str, Any]]: ...
    async def place_order(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def modify_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def get_funds(self) -> dict[str, Any]: ...
    async def get_margin(self) -> dict[str, Any]: ...
    async def get_trades(self) -> list[dict[str, Any]]: ...


def _load_adapter(provider_slug: Any, account: BrokerAccount) -> Any:
    """Load and instantiate the correct broker adapter using BrokerFactory."""
    from app.brokers.factory import BrokerFactory
    from app.core.config import settings

    factory = BrokerFactory()
    name_str = provider_slug.value if hasattr(provider_slug, "value") else str(provider_slug)
    slug = name_str.lower()
    credentials = {
        "client_id": account.account_id,
        "access_token": account.access_token or "",
    }

    if slug == "dhan":
        if settings.DHAN_PIN:
            credentials["pin"] = settings.DHAN_PIN
        if settings.DHAN_TOTP_SECRET:
            credentials["totp_secret"] = settings.DHAN_TOTP_SECRET
        if not credentials["access_token"] and settings.DHAN_ACCESS_TOKEN:
            credentials["access_token"] = settings.DHAN_ACCESS_TOKEN
    elif slug == "zerodha":
        if settings.ZERODHA_API_KEY:
            credentials["api_key"] = settings.ZERODHA_API_KEY
        if settings.ZERODHA_API_SECRET:
            credentials["api_secret"] = settings.ZERODHA_API_SECRET
        if settings.ZERODHA_USER_ID:
            credentials["user_id"] = settings.ZERODHA_USER_ID
        elif account.account_id:
            credentials["user_id"] = account.account_id
        if settings.ZERODHA_PASSWORD:
            credentials["password"] = settings.ZERODHA_PASSWORD
        if settings.ZERODHA_TOTP_SECRET:
            credentials["totp_secret"] = settings.ZERODHA_TOTP_SECRET
        if not credentials["access_token"] and settings.ZERODHA_ACCESS_TOKEN:
            credentials["access_token"] = settings.ZERODHA_ACCESS_TOKEN
    elif slug == "indmoney":
        if settings.INDMONEY_API_KEY:
            credentials["api_key"] = settings.INDMONEY_API_KEY
        if settings.INDMONEY_MPIN:
            credentials["mpin"] = settings.INDMONEY_MPIN
        if settings.INDMONEY_TOTP_SECRET:
            credentials["totp_secret"] = settings.INDMONEY_TOTP_SECRET
        if not credentials["access_token"] and settings.INDMONEY_ACCESS_TOKEN:
            credentials["access_token"] = settings.INDMONEY_ACCESS_TOKEN
    elif slug == "coindcx":
        if settings.COINDCX_API_KEY:
            credentials["api_key"] = settings.COINDCX_API_KEY
        if settings.COINDCX_API_SECRET:
            credentials["api_secret"] = settings.COINDCX_API_SECRET

    adapter = factory.create(slug, credentials)

    # If the adapter generated or updated the access token, synchronize it back to account
    if hasattr(adapter, "access_token") and adapter.access_token:
        if account.access_token != adapter.access_token:
            account.access_token = adapter.access_token

    return adapter


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BrokerService:
    """Application-layer service for broker provider and account management."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    async def get_providers(self, active_only: bool = True) -> List[BrokerProvider]:
        """Return the catalogue of supported broker integrations."""
        stmt = select(BrokerProvider)
        if active_only:
            stmt = stmt.where(BrokerProvider.is_active.is_(True))
        result = await self._db.execute(stmt.order_by(BrokerProvider.display_name))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # User accounts
    # ------------------------------------------------------------------

    async def get_user_accounts(
        self, user_id: int, active_only: bool = True
    ) -> List[BrokerAccount]:
        """Return all broker accounts linked to *user_id*."""
        stmt = (
            select(BrokerAccount)
            .options(selectinload(BrokerAccount.broker))
            .where(BrokerAccount.user_id == user_id)
        )
        if active_only:
            stmt = stmt.where(BrokerAccount.is_active.is_(True))
        result = await self._db.execute(stmt.order_by(BrokerAccount.created_at))
        accounts = list(result.scalars().all())
        for acct in accounts:
            self.inspect_account_token(acct)
        return accounts

    async def connect_account(
        self, user_id: int, payload: BrokerAccountCreate
    ) -> BrokerAccount:
        """
        Link a new broker account to the given user.

        If no other account exists for this user, the new account is
        automatically set as the default.

        Raises:
            ValueError: if the broker_id does not correspond to an active provider.
        """
        provider = await self._db.get(BrokerProvider, payload.broker_id)
        if not provider or not provider.is_active:
            raise ValueError(f"Broker provider {payload.broker_id} not found or inactive.")

        existing = await self.get_user_accounts(user_id)
        is_first = len(existing) == 0

        account = BrokerAccount(
            user_id=user_id,
            broker_id=payload.broker_id,
            account_id=payload.account_id,
            account_name=payload.account_name,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            is_active=True,
            is_default=is_first,
        )
        self._db.add(account)
        await self._db.commit()
        await self._db.refresh(account)
        return account

    async def update_account(
        self, account_id: int, user_id: int, payload: BrokerAccountUpdate
    ) -> BrokerAccount:
        """
        Apply partial updates to a broker account.

        If *is_default* is set to True, the previous default account (if any)
        is cleared first.

        Raises:
            ValueError: if the account is not found or does not belong to *user_id*.
        """
        account = await self._get_owned_account(account_id, user_id)

        update_data = payload.model_dump(exclude_unset=True)

        if update_data.get("is_default") is True:
            # Clear the existing default for this user
            existing_accounts = await self.get_user_accounts(user_id)
            for acc in existing_accounts:
                if acc.is_default and acc.id != account_id:
                    acc.is_default = False

        for field, value in update_data.items():
            setattr(account, field, value)

        if "access_token" in update_data and update_data["access_token"]:
            account.is_active = True
            self.inspect_account_token(account)

        await self._db.commit()
        await self._db.refresh(account)
        return account

    async def get_account(self, account_id: int, user_id: int) -> BrokerAccount:
        """Public alias for _get_owned_account."""
        return await self._get_owned_account(account_id, user_id)

    def inspect_account_token(self, account: BrokerAccount) -> None:
        """Inspect and populate token expiry and status on a BrokerAccount instance."""
        import base64
        import json
        from datetime import datetime, timezone
        from app.core.config import settings

        token = account.access_token or ""
        # Fallback to settings if token is empty
        provider_name = ""
        if account.broker:
            b_name = account.broker.name
            provider_name = b_name.value if hasattr(b_name, "value") else str(b_name)
        provider_name = provider_name.upper()

        if not token:
            if "INDMONEY" in provider_name and settings.INDMONEY_ACCESS_TOKEN:
                token = settings.INDMONEY_ACCESS_TOKEN
            elif "DHAN" in provider_name and settings.DHAN_ACCESS_TOKEN:
                token = settings.DHAN_ACCESS_TOKEN

        now = datetime.now(timezone.utc)
        exp_dt = account.token_expiry

        if token:
            # Check if JWT (3 parts separated by '.')
            clean_token = token.replace("Bearer ", "").strip()
            parts = clean_token.split(".")
            if len(parts) == 3:
                try:
                    payload_b64 = parts[1]
                    payload_b64 += "=" * (-len(payload_b64) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                    exp_ts = payload.get("exp")
                    if exp_ts:
                        exp_dt = datetime.fromtimestamp(exp_ts, timezone.utc)
                        account.token_expiry = exp_dt
                except Exception:
                    pass

        # Dhan: auto-relogin via PIN + TOTP handles sessions
        if "DHAN" in provider_name and settings.DHAN_PIN and settings.DHAN_TOTP_SECRET:
            account.token_status = "ACTIVE"
            account.is_token_expired = False
            account.status_message = "Automated login active"
            return

        # Zerodha: auto-relogin via TOTP/enctoken handles sessions
        if "ZERODHA" in provider_name and settings.ZERODHA_PASSWORD and settings.ZERODHA_TOTP_SECRET:
            account.token_status = "ACTIVE"
            account.is_token_expired = False
            account.status_message = "Automated login active"
            return

        # INDMoney: auto-relogin via TOTP handles sessions
        if "INDMONEY" in provider_name and settings.INDMONEY_MPIN and settings.INDMONEY_TOTP_SECRET:
            account.token_status = "ACTIVE"
            account.is_token_expired = False
            account.status_message = "Automated login active"
            return

        # CoinDCX: persistent API key authentication (with optional Options token)
        if "COINDCX" in provider_name:
            if settings.COINDCX_API_KEY and settings.COINDCX_API_SECRET:
                account.token_status = "ACTIVE"
                account.is_token_expired = False
                if exp_dt:
                    if exp_dt < now:
                        account.status_message = "API key active; Options token expired (click 🔑 to update)"
                    else:
                        account.status_message = f"Active (Options token valid until {exp_dt.strftime('%d %b %H:%M')})"
                else:
                    account.status_message = "API key active"
            else:
                has_cred = bool(account.access_token)
                account.token_status = "ACTIVE" if has_cred else "EXPIRED"
                account.is_token_expired = not has_cred
                account.status_message = None if has_cred else "API credentials missing"
            return

        if exp_dt:
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt < now:
                account.is_token_expired = True
                account.token_status = "EXPIRED"
                account.status_message = f"Token expired on {exp_dt.strftime('%d %b %Y')}"
            else:
                account.is_token_expired = False
                account.token_status = "ACTIVE"
                account.status_message = None
        else:
            if not token:
                account.is_token_expired = True
                account.token_status = "EXPIRED"
                account.status_message = "No token configured"
            else:
                account.is_token_expired = False
                account.token_status = "ACTIVE" if account.is_active else "INACTIVE"
                account.status_message = None

    async def disconnect_account(self, account_id: int, user_id: int) -> None:
        """
        Soft-delete a broker account by marking it inactive.

        Raises:
            ValueError: if the account is not found or does not belong to *user_id*.
        """
        account = await self._get_owned_account(account_id, user_id)
        account.is_active = False
        account.access_token = ""  # Revoke stored token
        account.refresh_token = None
        await self._db.commit()

    # ------------------------------------------------------------------
    # Adapter factory
    # ------------------------------------------------------------------

    async def get_broker_instance(
        self, account_id: int, user_id: int
    ) -> BrokerAdapter:
        """
        Return an initialised broker adapter for the given account.

        Raises:
            ValueError: if the account is not owned by *user_id*.
            NotImplementedError: if no adapter exists for the broker.
        """
        account = await self._get_owned_account(account_id, user_id)
        provider: BrokerProvider = await self._db.get(BrokerProvider, account.broker_id)  # type: ignore[assignment]
        adapter = _load_adapter(provider.name, account)
        if hasattr(adapter, "access_token") and adapter.access_token:
            if account.access_token != adapter.access_token:
                account.access_token = adapter.access_token
                await self._db.commit()
        return adapter

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_owned_account(self, account_id: int, user_id: int) -> BrokerAccount:
        stmt = (
            select(BrokerAccount)
            .options(selectinload(BrokerAccount.broker))
            .where(
                BrokerAccount.id == account_id,
                BrokerAccount.user_id == user_id,
            )
        )
        result = await self._db.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(
                f"BrokerAccount {account_id} not found for user {user_id}."
            )
        return account
