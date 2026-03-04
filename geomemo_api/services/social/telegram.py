"""
Telegram Bot API client for GeoMemo channel posting.
Uses direct HTTP requests (same pattern as Beehiiv integration in newsletter.py).
No extra dependencies — uses the existing `requests` library.
"""
import logging
import requests as http_requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


def is_configured() -> bool:
    """Check if Telegram credentials are set."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID)


def send_message(text: str, parse_mode: str = "HTML",
                 disable_web_page_preview: bool = False) -> dict:
    """
    Send a message to the GeoMemo Telegram channel.
    Returns dict with message_id and chat_id.
    """
    if not is_configured():
        raise ValueError("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID.")

    url = f"{TELEGRAM_API_BASE}{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    response = http_requests.post(url, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data.get('description', 'Unknown')}")

    return {
        "message_id": data["result"]["message_id"],
        "chat_id": str(data["result"]["chat"]["id"]),
    }
