"""Application configuration via pydantic-settings."""
from typing import List, Optional
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    POSTGRES_USER: str = "trading"
    POSTGRES_PASSWORD: str = "trading_secret"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "trading_platform"
    DATABASE_URL: Optional[str] = None

    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        if not self.DATABASE_URL:
            pwd = quote_plus(self.POSTGRES_PASSWORD)
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{pwd}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    SECRET_KEY: str = "changeme_in_production_32chars_min"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:80",
        "http://localhost",
    ]

    # Dhan
    DHAN_CLIENT_ID: str = ""
    DHAN_ACCESS_TOKEN: str = ""
    DHAN_PIN: str = ""
    DHAN_TOTP_SECRET: str = ""

    # Zerodha
    ZERODHA_USER_ID: str = ""
    ZERODHA_PASSWORD: str = ""
    ZERODHA_TOTP_SECRET: str = ""
    ZERODHA_API_KEY: str = ""
    ZERODHA_API_SECRET: str = ""
    ZERODHA_ACCESS_TOKEN: str = ""
    ZERODHA_REQUEST_TOKEN: str = ""

    # INDMoney (INDstocks API)
    INDMONEY_EMAIL: str = ""
    INDMONEY_PASSWORD: str = ""
    INDMONEY_CLIENT_ID: str = ""
    INDMONEY_ACCESS_TOKEN: str = ""
    INDMONEY_API_KEY: str = ""
    INDMONEY_MPIN: str = ""
    INDMONEY_TOTP_SECRET: str = ""

    # IBKR
    IBKR_HOST: str = "127.0.0.1"
    IBKR_PORT: int = 7497
    IBKR_CLIENT_ID: int = 1

    # CoinDCX (REST API)
    COINDCX_API_KEY: str = ""
    COINDCX_API_SECRET: str = ""
    COINDCX_AUTH_TOKEN: str = ""

    # Telegram Bot Alerts
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Encryption key for storing broker tokens in DB
    FERNET_KEY: str = ""


settings = Settings()
