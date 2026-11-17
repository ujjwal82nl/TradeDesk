"""
Broker management endpoints.

Handles listing supported brokers, connecting/disconnecting broker accounts,
and updating credentials.
"""

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.broker import (
    BrokerAccountCreate,
    BrokerAccountResponse,
    BrokerAccountUpdate,
    BrokerProviderResponse,
)
from app.services.broker_service import BrokerService

router = APIRouter()


class SyncResultResponse(BaseModel):
    """Result of a broker account sync operation."""

    synced_at: str
    holdings_synced: int = 0
    positions_synced: int = 0
    orders_synced: int = 0
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[BrokerProviderResponse],
    summary="List supported broker providers",
)
async def list_broker_providers(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[BrokerProviderResponse]:
    """Return the static catalogue of brokers that the platform supports."""
    service = BrokerService(db)
    providers = await service.get_providers()
    return [
        BrokerProviderResponse(
            id=p.id,
            name=p.name.value if hasattr(p.name, "value") else str(p.name),
            display_name=p.display_name,
            is_active=p.is_active,
        )
        for p in providers
    ]


@router.get(
    "/providers",
    response_model=List[BrokerProviderResponse],
    summary="List supported broker providers (alias)",
)
async def list_broker_providers_alias(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[BrokerProviderResponse]:
    """Alias for /brokers catalogue."""
    return await list_broker_providers(db)


@router.get(
    "/accounts",
    response_model=List[BrokerAccountResponse],
    summary="List user's connected broker accounts",
)
async def list_broker_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[BrokerAccountResponse]:
    """Return all broker accounts linked to the authenticated user."""
    service = BrokerService(db)
    accounts = await service.get_user_accounts(current_user.id, active_only=False)
    for a in accounts:
        service.inspect_account_token(a)
    return [BrokerAccountResponse.model_validate(a) for a in accounts]


@router.post(
    "/accounts",
    response_model=BrokerAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a new broker account",
)
async def connect_broker_account(
    payload: BrokerAccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BrokerAccountResponse:
    """Link a broker account to the authenticated user."""
    service = BrokerService(db)
    try:
        account = await service.connect_account(
            user_id=current_user.id,
            payload=payload,
        )
        service.inspect_account_token(account)
        return BrokerAccountResponse.model_validate(account)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/accounts/{account_id}",
    response_model=BrokerAccountResponse,
    summary="Update broker account",
)
async def update_broker_account(
    account_id: Annotated[int, Path(ge=1)],
    payload: BrokerAccountUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BrokerAccountResponse:
    """Update an existing broker account."""
    service = BrokerService(db)
    try:
        updated = await service.update_account(
            account_id=account_id,
            user_id=current_user.id,
            payload=payload,
        )
        service.inspect_account_token(updated)
        return BrokerAccountResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a broker account",
)
async def disconnect_broker_account(
    account_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Disconnect a linked broker account."""
    service = BrokerService(db)
    try:
        await service.disconnect_account(account_id=account_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/accounts/{account_id}/sync",
    response_model=SyncResultResponse,
    summary="Trigger manual sync for a broker account",
)
async def sync_broker_account(
    account_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyncResultResponse:
    """Trigger manual sync for a broker account and validate connection."""
    from datetime import datetime, timezone
    from app.services.holdings_service import HoldingsService
    from app.services.positions_service import PositionsService

    service = BrokerService(db)
    try:
        account = await service.get_account(account_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    service.inspect_account_token(account)
    if account.is_token_expired:
        return SyncResultResponse(
            synced_at=datetime.now(timezone.utc).isoformat(),
            errors=[
                f"Cannot sync: Access token expired on {account.token_expiry.strftime('%d %b %Y') if account.token_expiry else 'earlier date'}. Please update your token."
            ],
        )

    errors: List[str] = []
    holdings_count = 0
    positions_count = 0

    try:
        h_svc = HoldingsService(db, current_user.id)
        h_res = await h_svc.sync_holdings(broker_account_id=account_id)
        holdings_count = len(h_res)
    except Exception as exc:
        errors.append(f"Holdings sync error: {str(exc)}")

    try:
        p_svc = PositionsService(db, current_user.id)
        p_res = await p_svc.sync_positions(broker_account_id=account_id)
        positions_count = len(p_res)
    except Exception as exc:
        errors.append(f"Positions sync error: {str(exc)}")

    return SyncResultResponse(
        synced_at=datetime.now(timezone.utc).isoformat(),
        holdings_synced=holdings_count,
        positions_synced=positions_count,
        errors=errors,
    )
