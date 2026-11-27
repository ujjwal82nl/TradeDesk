"""User-related Pydantic schemas: registration, auth, profile management."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# User CRUD schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Payload for creating a new user account."""

    email: EmailStr = Field(..., description="User's unique email address.")
    password: str = Field(
        ..., min_length=8, description="Plain-text password (min 8 characters)."
    )
    full_name: str = Field(..., min_length=1, description="User's display name.")


class UserUpdate(BaseModel):
    """Partial update payload for user profile fields."""

    full_name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[EmailStr] = Field(default=None)


class UserResponse(BaseModel):
    """Serialised user record returned from the API."""

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Authentication schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Credentials payload for the login endpoint."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token pair returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Payload for the change-password endpoint."""

    old_password: str = Field(..., description="Current password for verification.")
    new_password: str = Field(
        ..., min_length=8, description="Replacement password (min 8 characters)."
    )
