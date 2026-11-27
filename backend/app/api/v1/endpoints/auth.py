"""
Authentication endpoints.

Covers registration, login, token refresh, profile management,
logout (refresh-token blacklisting), and password change.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class UserRegisterRequest(BaseModel):
    """Payload for new-user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str = Field(..., min_length=1, max_length=255)


class UserLoginRequest(BaseModel):
    """Payload for email/password login."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Payload for token refresh."""

    refresh_token: str


class AccessTokenResponse(BaseModel):
    """New access token returned after refresh."""

    access_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    """Public user profile."""

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Partial profile update payload."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None


class LogoutRequest(BaseModel):
    """Payload for logout – client supplies the refresh token to blacklist."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Payload for password change."""

    current_password: str
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    """
    Create a new user account.

    Raises **409** if the email is already registered.
    """
    from app.services.auth_service import AuthService

    service = AuthService(db)
    existing = await service.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )
    user = await service.create_user(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    return UserProfileResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and obtain JWT tokens",
)
async def login(
    payload: UserLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Authenticate with email and password.

    Returns a short-lived **access token** and a long-lived **refresh token**.
    Raises **401** on invalid credentials or inactive account.
    """
    from app.services.auth_service import AuthService

    service = AuthService(db)
    user = await service.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated.",
        )
    tokens = await service.create_tokens(user)
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessTokenResponse:
    """
    Exchange a valid refresh token for a new access token.

    Raises **401** if the refresh token is invalid, expired, or blacklisted.
    """
    from app.services.auth_service import AuthService

    service = AuthService(db)
    access_token = await service.refresh_access_token(payload.refresh_token)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AccessTokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: Annotated[object, Depends(get_current_user)],
) -> UserProfileResponse:
    """Return the authenticated user's profile."""
    return UserProfileResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update current user profile",
)
async def update_me(
    payload: UpdateProfileRequest,
    current_user: Annotated[object, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    """
    Update mutable profile fields (full_name, email).

    Raises **409** if the new email belongs to another account.
    """
    from app.services.auth_service import AuthService

    service = AuthService(db)
    if payload.email and payload.email != current_user.email:
        conflict = await service.get_user_by_email(payload.email)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already in use.",
            )
    updated = await service.update_user(
        user=current_user,
        full_name=payload.full_name,
        email=payload.email,
    )
    return UserProfileResponse.model_validate(updated)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout – blacklist refresh token",
)
async def logout(
    payload: LogoutRequest,
    current_user: Annotated[object, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Invalidate the supplied refresh token so it cannot be reused.

    The client should discard both access and refresh tokens after calling this.
    """
    from app.services.auth_service import AuthService

    service = AuthService(db)
    await service.blacklist_token(payload.refresh_token)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change account password",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[object, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Change the authenticated user's password.

    Raises **400** if the current password is wrong.
    All existing refresh tokens are invalidated after a successful change.
    """
    from app.services.auth_service import AuthService

    service = AuthService(db)
    success = await service.change_password(
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
