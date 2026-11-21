"""CLI utility to manage TradeDesk users (create admin, list, delete demo users).

Usage examples:
    python scripts/manage_users.py list
    python scripts/manage_users.py add --email user@example.com --password "SecurePass123!" --name "Ujjwal" --admin
    python scripts/manage_users.py delete --email admin@trading.com
    python scripts/manage_users.py delete-defaults
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, delete
from app.db.session import async_session_factory
from app.models.user import User
from app.core.security import get_password_hash


async def list_users():
    async with async_session_factory() as db:
        res = await db.execute(select(User).order_by(User.id))
        users = res.scalars().all()
        if not users:
            print("No users found.")
            return
        print(f"\n{'ID':<5} {'Email':<30} {'Name':<20} {'Active':<8} {'Superuser':<10}")
        print("-" * 75)
        for u in users:
            print(f"{u.id:<5} {u.email:<30} {u.full_name or '':<20} {str(u.is_active):<8} {str(u.is_superuser):<10}")
        print()


async def add_or_update_user(email: str, password: str, name: str, is_admin: bool):
    async with async_session_factory() as db:
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if user:
            user.hashed_password = get_password_hash(password)
            user.full_name = name
            user.is_superuser = is_admin
            user.is_active = True
            await db.commit()
            print(f"Updated user: {email} (Admin: {is_admin})")
        else:
            user = User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name=name,
                is_active=True,
                is_superuser=is_admin,
            )
            db.add(user)
            await db.commit()
            print(f"Created new user: {email} (Admin: {is_admin})")


async def delete_user(email: str):
    async with async_session_factory() as db:
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user:
            print(f"User {email} not found.")
            return
        await db.execute(delete(User).where(User.email == email))
        await db.commit()
        print(f"Deleted user: {email}")


async def delete_defaults():
    async with async_session_factory() as db:
        res = await db.execute(delete(User).where(User.email.in_(["admin@trading.com", "admin@trading.local"])))
        await db.commit()
        print("Deleted demo accounts (admin@trading.com, admin@trading.local).")


def main():
    parser = argparse.ArgumentParser(description="Manage TradeDesk users")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all users")

    # add
    add_parser = subparsers.add_parser("add", help="Add or update a user")
    add_parser.add_argument("--email", required=True, help="User email")
    add_parser.add_argument("--password", required=True, help="Password (min 8 characters)")
    add_parser.add_argument("--name", default="Admin", help="Full name")
    add_parser.add_argument("--admin", action="store_true", default=True, help="Set as superuser / admin")

    # delete
    del_parser = subparsers.add_parser("delete", help="Delete a specific user")
    del_parser.add_argument("--email", required=True, help="Email of user to delete")

    # delete-defaults
    subparsers.add_parser("delete-defaults", help="Delete demo admin@trading.* accounts")

    args = parser.parse_args()

    if args.command == "list":
        asyncio.run(list_users())
    elif args.command == "add":
        if len(args.password) < 8:
            print("Error: Password must be at least 8 characters long.")
            sys.exit(1)
        asyncio.run(add_or_update_user(args.email, args.password, args.name, args.admin))
    elif args.command == "delete":
        asyncio.run(delete_user(args.email))
    elif args.command == "delete-defaults":
        asyncio.run(delete_defaults())


if __name__ == "__main__":
    main()
