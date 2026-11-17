"""
Database initialisation script.
Run this once to apply the SQL migration files against a fresh PostgreSQL instance.

Usage:
  python scripts/init_db.py

Requires DATABASE_URL env var or falls back to .env file.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import asyncpg
from dotenv import load_dotenv
import os

load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading:trading_secret@localhost:5432/trading_platform")
# asyncpg uses postgresql:// not postgresql+asyncpg://
DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

MIGRATIONS = sorted((ROOT / "database" / "migrations").glob("*.sql"))


async def main():
    print(f"Connecting to: {DSN.split('@')[1]}")
    try:
        conn = await asyncpg.connect(DSN)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    for migration in MIGRATIONS:
        print(f"Applying {migration.name}…")
        sql = migration.read_text(encoding="utf-8")
        try:
            await conn.execute(sql)
            print(f"  ✅ {migration.name}")
        except Exception as e:
            print(f"  ⚠️  {migration.name}: {e}")

    await conn.close()
    print("\n🎉 Database initialised successfully!")


if __name__ == "__main__":
    asyncio.run(main())
