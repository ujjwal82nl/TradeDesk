"""
Telegram Bot Service for delivering real-time trading signals and alerts.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramService:
    """Service to interact with Telegram Bot API."""

    @classmethod
    def get_token(cls, override_token: Optional[str] = None) -> str:
        token = (override_token or settings.TELEGRAM_BOT_TOKEN or "").strip()
        return token

    @classmethod
    def get_chat_id(cls, override_chat_id: Optional[str] = None) -> str:
        chat_id = (override_chat_id or settings.TELEGRAM_CHAT_ID or "").strip()
        return chat_id

    @classmethod
    async def get_bot_info(cls, bot_token: Optional[str] = None) -> Dict[str, Any]:
        """Fetch bot info to verify credentials (getMe)."""
        token = cls.get_token(bot_token)
        if not token:
            return {"success": False, "error": "Telegram Bot Token not configured"}

        url = f"{TELEGRAM_API_BASE}/bot{token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                data = res.json()
                if res.status_code == 200 and data.get("ok"):
                    result = data.get("result", {})
                    return {
                        "success": True,
                        "bot_id": result.get("id"),
                        "username": result.get("username"),
                        "first_name": result.get("first_name"),
                        "can_join_groups": result.get("can_join_groups"),
                    }
                return {"success": False, "error": data.get("description", f"HTTP {res.status_code}")}
        except Exception as exc:
            log.warning("telegram_get_bot_info_error", error=str(exc))
            return {"success": False, "error": str(exc)}

    @classmethod
    async def auto_detect_chat_id(cls, bot_token: Optional[str] = None) -> Dict[str, Any]:
        """Check getUpdates to detect recent chat_id if user sent a message to the bot."""
        token = cls.get_token(bot_token)
        if not token:
            return {"success": False, "error": "Telegram Bot Token not configured"}

        info = await cls.get_bot_info(token)
        bot_id = str(info.get("bot_id") or "")
        bot_name = info.get("username") or "your bot"

        url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                data = res.json()
                if res.status_code == 200 and data.get("ok"):
                    updates = data.get("result", [])
                    if not updates:
                        return {
                            "success": False,
                            "error": f"No messages received yet. Please open Telegram, search for @{bot_name}, click 'Start' (or send /start), and then click Auto-Detect again.",
                        }
                    # Look backwards for the most recent message from a human user or group/channel
                    for upd in reversed(updates):
                        msg = upd.get("message") or upd.get("channel_post") or upd.get("my_chat_member")
                        if msg:
                            from_user = msg.get("from") or {}
                            chat = msg.get("chat") or {}
                            chat_id_val = str(chat.get("id") or "")
                            from_id_val = str(from_user.get("id") or "")

                            # Make sure it is not the bot itself!
                            target_id = None
                            if chat_id_val and chat_id_val != bot_id:
                                target_id = chat_id_val
                            elif from_id_val and from_id_val != bot_id and not from_user.get("is_bot"):
                                target_id = from_id_val

                            if target_id:
                                return {
                                    "success": True,
                                    "chat_id": target_id,
                                    "chat_type": chat.get("type", "private"),
                                    "username": from_user.get("username") or chat.get("username"),
                                    "first_name": from_user.get("first_name") or chat.get("first_name") or chat.get("title"),
                                }

                    return {
                        "success": False,
                        "error": f"Could not find a human user chat in updates. Please send /start to @{bot_name} from your Telegram account.",
                    }
                return {"success": False, "error": data.get("description", f"HTTP {res.status_code}")}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    async def send_message(
        cls,
        text: str,
        chat_id: Optional[str] = None,
        bot_token: Optional[str] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        """Send message to a Telegram chat."""
        token = cls.get_token(bot_token)
        cid = cls.get_chat_id(chat_id)

        if not token:
            return {"success": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}
        if not cid:
            return {"success": False, "error": "TELEGRAM_CHAT_ID is not configured"}

        # Check if user accidentally entered the bot's own ID as chat_id
        token_bot_id = token.split(":")[0].strip() if ":" in token else ""
        if token_bot_id and str(cid).strip() == token_bot_id:
            return {
                "success": False,
                "error": (
                    f"Chat ID ({cid}) is the bot's own user ID! A bot cannot send messages to itself. "
                    "You need your personal Telegram Chat ID (or channel/group ID). "
                    "Open Telegram, send /start to your bot, then click 'Auto-Detect Chat ID' (or ask @userinfobot)."
                ),
            }

        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
        payload = {
            "chat_id": cid,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload)
                data = res.json()
                if res.status_code == 200 and data.get("ok"):
                    log.info("telegram_message_sent", chat_id=cid, message_id=data["result"].get("message_id"))
                    return {
                        "success": True,
                        "message_id": data["result"].get("message_id"),
                        "chat_id": cid,
                    }
                err_desc = data.get("description", f"HTTP {res.status_code}")
                if "can't send messages to the bot" in err_desc.lower():
                    err_desc = (
                        f"The Chat ID provided ({cid}) is a bot ID! A bot cannot message a bot. "
                        "Please use your personal Telegram Chat ID instead."
                    )
                log.warning("telegram_send_failed", status=res.status_code, response=data)
                return {"success": False, "error": err_desc}
        except Exception as exc:
            log.error("telegram_send_exception", error=str(exc))
            return {"success": False, "error": str(exc)}

    @classmethod
    async def test_connection(
        cls,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify bot credentials and send a test message."""
        info = await cls.get_bot_info(bot_token)
        if not info.get("success"):
            return info

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        bot_handle = f"@{info.get('username')}" if info.get("username") else info.get("first_name", "Bot")
        test_msg = (
            f"🔔 <b>TradeDesk Telegram Alert Connected!</b>\n\n"
            f"🤖 <b>Bot:</b> {bot_handle}\n"
            f"⏱ <b>Timestamp:</b> <code>{now_str}</code>\n\n"
            f"✅ <i>Your TradeDesk application is connected. Indicator signals (SuperTrend, breakouts, flips) will be delivered to this chat.</i>"
        )

        send_res = await cls.send_message(
            text=test_msg,
            chat_id=chat_id,
            bot_token=bot_token,
        )

        if send_res.get("success"):
            return {
                "success": True,
                "message": f"Successfully connected to {bot_handle} and delivered test alert!",
                "bot_info": info,
                "chat_id": send_res.get("chat_id"),
            }
        return {
            "success": False,
            "error": f"Bot valid ({bot_handle}), but could not send message: {send_res.get('error')}",
            "bot_info": info,
        }

    @classmethod
    def format_supertrend_alert(
        cls,
        symbol: str,
        old_signal: Optional[str],
        new_signal: str,
        spot_price: float,
        indicator_value: float,
        timeframe: str = "90 mins",
        params: Optional[dict] = None,
    ) -> str:
        """Format a rich HTML alert message for SuperTrend signal flip."""
        params = params or {"period": 16, "multiplier": 1.5}
        period = params.get("period", 16)
        mult = params.get("multiplier", 1.5)

        is_bullish = new_signal.upper() in ("GREEN", "BUY")
        signal_badge = "🟢 <b>BULLISH (BUY / GREEN)</b>" if is_bullish else "🔴 <b>BEARISH (SELL / RED)</b>"
        prev_badge = "🔴 RED" if is_bullish else "🟢 GREEN"
        if not old_signal:
            prev_badge = "INITIAL STATE"
        elif old_signal.upper() in ("GREEN", "BUY"):
            prev_badge = "🟢 GREEN"
        elif old_signal.upper() in ("RED", "SELL"):
            prev_badge = "🔴 RED"

        header_emoji = "🚀" if is_bullish else "🔻"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Format prices cleanly
        spot_fmt = f"${spot_price:,.2f}" if spot_price > 10 else f"${spot_price:.6f}"
        st_fmt = f"${indicator_value:,.2f}" if indicator_value > 10 else f"${indicator_value:.6f}"

        msg = (
            f"{header_emoji} <b>SUPERTREND SIGNAL FLIP: {symbol.upper()}</b> {header_emoji}\n\n"
            f"📊 <b>Instrument:</b> <code>{symbol.upper()}</code>\n"
            f"⏱ <b>Time Interval:</b> <code>{timeframe}</code>\n"
            f"📐 <b>Parameters:</b> Period={period}, Multiplier={mult}\n\n"
            f"⚡ <b>Signal Changed:</b> {prev_badge} ➔ {signal_badge}\n"
            f"💰 <b>Current Spot Price:</b> <b>{spot_fmt}</b>\n"
            f"🎯 <b>SuperTrend Value:</b> <b>{st_fmt}</b>\n"
            f"🕒 <b>Trigger Time:</b> <code>{now_str}</code>\n\n"
            f"🔔 <i>TradeDesk Automated Indicator Alert Engine</i>"
        )
        return msg

