"""
factory.py – BrokerFactory: creates and validates broker adapter instances.

Usage::

    factory = BrokerFactory()
    broker = factory.create("dhan", {"client_id": "...", "access_token": "..."})
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Type

from app.brokers.adapters.coindcx_adapter import CoinDCXAdapter
from app.brokers.adapters.dhan_adapter import DhanAdapter
from app.brokers.adapters.ibkr_adapter import IBKRAdapter
from app.brokers.adapters.indmoney_adapter import INDMoneyAdapter
from app.brokers.adapters.zerodha_adapter import ZerodhaAdapter
from app.brokers.base import BaseBroker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credential schemas
# Each entry maps a broker name → frozenset of required credential keys.
# ---------------------------------------------------------------------------

_REQUIRED_CREDENTIALS: Dict[str, frozenset] = {
    "dhan": frozenset({"client_id"}),  # Requires client_id + (access_token OR [pin + totp_secret])
    "zerodha": frozenset({"user_id"}),
    "indmoney": frozenset(),  # Requires access_token OR [api_key/client_id + mpin + totp_secret]
    "ibkr": frozenset({"host", "port", "client_id"}),
    "coindcx": frozenset({"api_key", "api_secret"}),
}

# ---------------------------------------------------------------------------
# Broker registry
# Maps lowercase broker name → adapter class.
# ---------------------------------------------------------------------------

_BROKER_REGISTRY: Dict[str, Type[BaseBroker]] = {
    "dhan": DhanAdapter,
    "zerodha": ZerodhaAdapter,
    "indmoney": INDMoneyAdapter,
    "ibkr": IBKRAdapter,
    "coindcx": CoinDCXAdapter,
}


class BrokerFactory:
    """Factory for creating :class:`BaseBroker` adapter instances.

    Adapter classes are registered in ``_BROKER_REGISTRY``.  You can
    extend the registry at runtime with :meth:`register`.

    Example::

        factory = BrokerFactory()

        dhan = factory.create("dhan", {
            "client_id": "YOUR_CLIENT_ID",
            "access_token": "YOUR_ACCESS_TOKEN",
        })

        zerodha = factory.create("zerodha", {
            "api_key": "YOUR_API_KEY",
            "access_token": "YOUR_SESSION_TOKEN",
        })
    """

    def __init__(self) -> None:
        # Instance-level copy so callers can register without affecting globals.
        self._registry: Dict[str, Type[BaseBroker]] = dict(_BROKER_REGISTRY)
        self._required: Dict[str, frozenset] = dict(_REQUIRED_CREDENTIALS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        broker_name: str,
        adapter_class: Type[BaseBroker],
        required_credentials: frozenset,
    ) -> None:
        """Register a new broker adapter at runtime.

        Args:
            broker_name: Lowercase string key (e.g. ``"fyers"``).
            adapter_class: A class that inherits from :class:`BaseBroker`.
            required_credentials: ``frozenset`` of required credential keys.

        Raises:
            ValueError: If *adapter_class* does not inherit from
                        :class:`BaseBroker`.
        """
        if not issubclass(adapter_class, BaseBroker):
            raise ValueError(
                f"{adapter_class.__name__} must be a subclass of BaseBroker"
            )
        key = broker_name.lower()
        self._registry[key] = adapter_class
        self._required[key] = required_credentials
        logger.info("BrokerFactory.register: registered broker '%s'", key)

    def supported_brokers(self) -> list[str]:
        """Return a sorted list of all registered broker names."""
        return sorted(self._registry.keys())

    def create(self, broker_name: str, credentials: Dict[str, Any]) -> BaseBroker:
        """Instantiate and return the appropriate broker adapter.

        Args:
            broker_name: Name of the broker (case-insensitive).
                         Supported values: ``"dhan"``, ``"zerodha"``,
                         ``"indmoney"``, ``"ibkr"``.
            credentials: Dict of credential key/value pairs.

        Returns:
            A configured :class:`BaseBroker` instance.

        Raises:
            ValueError: If *broker_name* is not registered or *credentials*
                        are missing required keys.
        """
        key = broker_name.lower().strip()

        if key not in self._registry:
            available = ", ".join(self.supported_brokers())
            raise ValueError(
                f"Unknown broker '{broker_name}'. Available: {available}"
            )

        self._validate_credentials(key, credentials)

        adapter_class = self._registry[key]
        logger.info("BrokerFactory.create: creating %s adapter", key)

        return self._instantiate(key, adapter_class, credentials)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_credentials(self, broker_name: str, credentials: Dict[str, Any]) -> None:
        """Raise ``ValueError`` if any required credential keys are absent or blank."""
        if broker_name == "dhan":
            client_id = credentials.get("client_id")
            if not client_id:
                raise ValueError("Invalid credentials for broker 'dhan': missing 'client_id'")
            has_token = bool(credentials.get("access_token"))
            has_totp = bool(credentials.get("pin") and credentials.get("totp_secret"))
            if not (has_token or has_totp):
                raise ValueError(
                    "Invalid credentials for broker 'dhan': either 'access_token' or both 'pin' and 'totp_secret' are required"
                )
            return

        if broker_name == "zerodha":
            has_token = bool(credentials.get("access_token"))
            has_enctoken_login = bool(
                (credentials.get("user_id") or credentials.get("client_id"))
                and credentials.get("password")
                and credentials.get("totp_secret")
            )
            has_api_login = bool(
                credentials.get("api_key")
                and (
                    credentials.get("access_token")
                    or (
                        credentials.get("api_secret")
                        and (credentials.get("user_id") or credentials.get("client_id"))
                        and credentials.get("password")
                        and credentials.get("totp_secret")
                    )
                )
            )
            if not (has_token or has_enctoken_login or has_api_login):
                raise ValueError(
                    "Invalid credentials for broker 'zerodha': either 'access_token' or credentials ('user_id', 'password', 'totp_secret') are required"
                )
            return

        if broker_name == "indmoney":
            has_token = bool(credentials.get("access_token"))
            has_totp = bool(
                (credentials.get("api_key") or credentials.get("client_id"))
                and credentials.get("mpin")
                and credentials.get("totp_secret")
            )
            if not (has_token or has_totp):
                raise ValueError(
                    "Invalid credentials for broker 'indmoney': either 'access_token' or credentials ('api_key'/'client_id', 'mpin', 'totp_secret') are required"
                )
            return

        required = self._required.get(broker_name, frozenset())
        missing: list[str] = []
        blank: list[str] = []

        for key in required:
            if key not in credentials:
                missing.append(key)
            elif not credentials[key]:
                blank.append(key)

        errors: list[str] = []
        if missing:
            errors.append(f"missing keys: {', '.join(sorted(missing))}")
        if blank:
            errors.append(f"blank/empty values for: {', '.join(sorted(blank))}")

        if errors:
            raise ValueError(
                f"Invalid credentials for broker '{broker_name}': {'; '.join(errors)}"
            )

    @staticmethod
    def _instantiate(
        broker_name: str,
        adapter_class: Type[BaseBroker],
        credentials: Dict[str, Any],
    ) -> BaseBroker:
        """Construct the adapter from *credentials*, dispatching by broker name."""
        if broker_name == "dhan":
            return adapter_class(  # type: ignore[call-arg]
                client_id=credentials["client_id"],
                access_token=credentials.get("access_token"),
                pin=credentials.get("pin"),
                totp_secret=credentials.get("totp_secret"),
            )
        if broker_name == "zerodha":
            return adapter_class(  # type: ignore[call-arg]
                api_key=credentials.get("api_key", ""),
                access_token=credentials.get("access_token"),
                api_secret=credentials.get("api_secret"),
                user_id=credentials.get("user_id") or credentials.get("client_id"),
                password=credentials.get("password"),
                totp_secret=credentials.get("totp_secret"),
            )
        if broker_name == "indmoney":
            return adapter_class(  # type: ignore[call-arg]
                access_token=credentials.get("access_token", ""),
                client_id=credentials.get("client_id", ""),
                email=credentials.get("email", ""),
                password=credentials.get("password", ""),
                api_key=credentials.get("api_key", ""),
                mpin=credentials.get("mpin", ""),
                totp_secret=credentials.get("totp_secret", ""),
            )
        if broker_name == "coindcx":
            return adapter_class(  # type: ignore[call-arg]
                api_key=credentials.get("api_key", ""),
                api_secret=credentials.get("api_secret", ""),
                client_id=credentials.get("client_id", ""),
                auth_token=credentials.get("access_token", "") or getattr(settings, "COINDCX_AUTH_TOKEN", ""),
            )
        if broker_name == "ibkr":
            return adapter_class(  # type: ignore[call-arg]
                host=credentials["host"],
                port=int(credentials["port"]),
                client_id=int(credentials["client_id"]),
            )

        # Generic fallback: attempt keyword-argument construction.
        # This handles dynamically registered adapters where argument names
        # exactly match credential keys.
        try:
            return adapter_class(**credentials)  # type: ignore[call-arg]
        except TypeError as exc:
            raise ValueError(
                f"Cannot construct adapter for '{broker_name}' from credentials: {exc}"
            ) from exc
