"""Auth service: user management + token operations."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.models.user import User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, email: str, password: str, full_name: str) -> User:
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        user = await self.get_user_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

    async def create_tokens(self, user: User) -> dict:
        return {
            "access_token":  create_access_token({"sub": str(user.id)}),
            "refresh_token": create_refresh_token({"sub": str(user.id)}),
        }

    async def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                return None
            user_id = int(payload["sub"])
        except Exception:
            return None
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None
        return create_access_token({"sub": str(user.id)})

    async def update_user(
        self, user: User, full_name: Optional[str] = None, email: Optional[str] = None
    ) -> User:
        if full_name is not None:
            user.full_name = full_name
        if email is not None:
            user.email = email
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(self, user: User, current_password: str, new_password: str) -> bool:
        if not verify_password(current_password, user.hashed_password):
            return False
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        return True

    async def blacklist_token(self, refresh_token: str) -> None:
        """
        Token blacklisting: in production, store invalidated tokens in Redis
        with a TTL equal to the token's remaining lifetime.
        For simplicity, this is a no-op stub — tokens expire naturally.
        """
        pass
