"""Button that sends users to the separate sales bot (TELE_SHOPS) - task 104.

The sales bot is a different Telegram bot, so this is a plain URL button (deep link), never callback_data.
Its username is NOT hardcoded: it comes from the SHOP_BOT_USERNAME environment variable, read at call time.
When it is missing or invalid the button is simply not shown.
"""
import os
import re
from typing import List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

AI_PRODUCTS_BUTTON_TEXT = "Mua AI Products (Gemini/ChatGPT)"
# TELE_SHOPS /start ignores payloads today, so no ?start=ai_products. Set to e.g. "ai_products" once it supports it.
SHOP_START_PAYLOAD = ""
_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def shop_bot_username() -> Optional[str]:
    raw = (os.getenv("SHOP_BOT_USERNAME") or "").strip()
    if raw.startswith("@"):
        raw = raw[1:]
    return raw if _USERNAME_RE.match(raw) else None


def shop_bot_url() -> Optional[str]:
    username = shop_bot_username()
    if not username:
        return None
    url = f"https://t.me/{username}"
    return f"{url}?start={SHOP_START_PAYLOAD}" if SHOP_START_PAYLOAD else url


def ai_products_button() -> Optional[InlineKeyboardButton]:
    url = shop_bot_url()
    return InlineKeyboardButton(text=AI_PRODUCTS_BUTTON_TEXT, url=url) if url else None


def with_ai_products_button(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    """Keyboard of `rows` plus the AI Products button as its own last row (when configured)."""
    rows = [list(r) for r in rows]
    button = ai_products_button()
    if button:
        rows.append([button])
    return InlineKeyboardMarkup(inline_keyboard=rows)
