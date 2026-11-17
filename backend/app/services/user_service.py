"""User service: CRUD operations and authentication."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_user(self, data: UserCreate) -> User:
        user = User(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(self, user: User, data: UserUpdate) -> User:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(self, user: User, old_password: str, new_password: str) -> bool:
        if not verify_password(old_password, user.hashed_password):
            return False
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        return True

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        user = await self.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user
