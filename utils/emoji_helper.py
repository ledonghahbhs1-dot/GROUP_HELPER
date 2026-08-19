import html
import re
from typing import Dict, List, Optional
from aiogram.exceptions import TelegramBadRequest
import config
from database.db import db

class EmojiManager:
    """
    Helper to render Telegram Premium Custom Emojis using <tg-emoji emoji-id="ID">Fallback</tg-emoji>
    """
    def __init__(self):
        self._db_emojis: Dict[str, Dict[str, str]] = {}

    async def load_emojis(self):
        """Loads customized emojis from DB and merges with config"""
        try:
            self._db_emojis = await db.get_all_custom_emojis()
        except Exception:
            self._db_emojis = {}

    def get(self, key: str, fallback_override: Optional[str] = None) -> str:
        """
        Returns formatted HTML tg-emoji tag or standard emoji fallback
        """
        key_lower = key.lower().strip()
        emoji_id = ""
        fallback = fallback_override or ""

        # Check DB first
        if key_lower in self._db_emojis:
            emoji_id = self._db_emojis[key_lower].get("id", "").strip()
            if not fallback:
                fallback = self._db_emojis[key_lower].get("fallback", "")

        # Fallback to config
        if not emoji_id and key_lower in config.DEFAULT_EMOJIS:
            emoji_id = config.DEFAULT_EMOJIS[key_lower].get("id", "").strip()
            if not fallback:
                fallback = config.DEFAULT_EMOJIS[key_lower].get("fallback", "")

        if not fallback:
            fallback = "✨"

        if emoji_id and emoji_id.isdigit():
            return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
        return fallback

    # Custom Emojis requested by user (Real valid IDs)
    @property
    def tele_logo(self) -> str:
        return self.get("tele_logo", "✈️")

    @property
    def clock(self) -> str:
        return self.get("clock", "⏳")

    @property
    def signature(self) -> str:
        """Required footer for every message: [5211129162206560202] :@wolfmodyt"""
        return f"\n\n{self.tele_logo} :@wolfmodyt"

    def format_msg(self, text: str) -> str:
        """Appends the mandatory signature to the message"""
        return f"{text}{self.signature}"

    def strip_tg_emojis(self, text: str) -> str:
        """Strips <tg-emoji> tags down to standard fallback emojis in case of invalid custom IDs"""
        return re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text)

    # Convenient VIP Emoji methods
    @property
    def vip(self) -> str:
        return self.get("vip", "👑")

    @property
    def shield(self) -> str:
        return self.get("shield", "🛡️")

    @property
    def warn(self) -> str:
        return self.get("warn", "⚠️")

    @property
    def ban(self) -> str:
        return self.get("ban", "🚫")

    @property
    def mute(self) -> str:
        return self.get("mute", "🔇")

    @property
    def link(self) -> str:
        return self.get("link", "🔗")

    @property
    def bot(self) -> str:
        return self.get("bot", "🤖")

    @property
    def spam(self) -> str:
        return self.get("spam", "🔥")

    @property
    def success(self) -> str:
        return self.get("success", "✅")

    @property
    def error(self) -> str:
        return self.get("error", "❌")

    @property
    def settings(self) -> str:
        return self.get("settings", "⚙️")

    @property
    def diamond(self) -> str:
        return self.get("diamond", "💎")

    @property
    def star(self) -> str:
        return self.get("star", "⭐")

    @property
    def lock(self) -> str:
        return self.get("lock", "🔒")

    @property
    def bell(self) -> str:
        return self.get("bell", "🔔")

    @property
    def admin(self) -> str:
        """Returns VIP Crown icon for Administrators"""
        return self.get("vip", "👑")

from utils.logger import logger

emoji_mgr = EmojiManager()

async def _try_send_stripping_bad_emojis(send_fn, text: str, **kwargs):
    """
    Attempts to send `text`. If Telegram rejects it (DOCUMENT_INVALID),
    strips one bad <tg-emoji> tag at a time (re-scanning after each strip)
    until the message sends or all custom emojis are stripped.
    """
    TG_EMOJI_RE = re.compile(r'<tg-emoji emoji-id=["\']([^"\']+)["\']>([^<]*)</tg-emoji>')
    current_text = text
    bad_ids: set = set()

    while True:
        try:
            return await send_fn(current_text, **kwargs)
        except TelegramBadRequest as e:
            err_str = str(e)
            if "DOCUMENT_INVALID" not in err_str and "can't parse" not in err_str:
                raise

            # Find first emoji ID not yet known to be bad
            match = TG_EMOJI_RE.search(current_text)
            if not match:
                # No more tg-emoji tags — last resort: strip all
                return await send_fn(emoji_mgr.strip_tg_emojis(text), **kwargs)

            # Binary: strip only THIS tag and retry
            bad_id = match.group(1)
            fallback = match.group(2)
            if bad_id not in bad_ids:
                bad_ids.add(bad_id)
                logger.warning("Custom emoji ID %s caused DOCUMENT_INVALID — stripping it", bad_id)

            # Replace ALL occurrences of this specific ID in current_text
            current_text = re.sub(
                r'<tg-emoji emoji-id=["\']' + re.escape(bad_id) + r'["\']>([^<]*)</tg-emoji>',
                r'\1',
                current_text
            )


async def safe_answer(message, text: str, **kwargs):
    """Safely answers a message, stripping only invalid VIP custom emoji IDs to keep all valid ones"""
    return await _try_send_stripping_bad_emojis(message.answer, text, **kwargs)


async def safe_send_message(bot, chat_id: int, text: str, **kwargs):
    """Safely sends a message, stripping only invalid VIP custom emoji IDs to keep all valid ones"""
    import functools
    send_fn = functools.partial(bot.send_message, chat_id)
    return await _try_send_stripping_bad_emojis(send_fn, text, **kwargs)

async def _delayed_delete(msg, delay: int):
    try:
        import asyncio
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass

def schedule_auto_delete(msg, delay_sec: int = 30):
    """Schedules a non-blocking background task to auto-delete msg after delay_sec seconds"""
    if msg:
        import asyncio
        asyncio.create_task(_delayed_delete(msg, delay_sec))

def get_payment_info_text() -> str:
    """Returns formatted VIP Payment Methods message using exclusively Premium VIP custom emojis"""
    return (
        f"{emoji_mgr.diamond} <b>PAYMENT METHODS</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>PayPal [GLOBAL]:</b> <code>paypal.me/WolfmodYT197</code>\n"
        f"   └ <b>GMAIL PAYPAL:</b> <code>ledongha2k7@gmail.com</code>\n\n"
        f"{emoji_mgr.star} <b>Binance ID [GLOBAL]:</b> <code>1158594960</code>\n"
        f"   └ <b>Deposit Address:</b> <code>0xff924e6b692567a4d9462a3bbef33f48a138dd2e</code> (network bep20)\n\n"
        f"{emoji_mgr.star} <b>SociaBuzz TRIBE:</b> <a href=\"https://sociabuzz.com/ldh/tribe\">LINK</a>\n\n"
        f"{emoji_mgr.star} <b>VCB (Vietcombank) [VIETNAM]:</b> <code>9382382864</code> | <b>LE DONG HA</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.warn} <i>Please send the correct information.</i>\n"
        f"{emoji_mgr.warn} <i>Please send by <b>FRIENDS AND FAMILY OPTION</b> !</i>\n"
        f"{emoji_mgr.diamond} <b>Note:</b> You can also redeem codes via <a href=\"https://rewarble.com/\">rewarble.com</a>\n\n"
        f"{emoji_mgr.star} <b>After sending, please DM</b> {emoji_mgr.vip} :@wolfmodyt {emoji_mgr.vip} <b>to confirm.</b>"
    )

def get_script_tool_info_text() -> str:
    """Returns formatted VIP Dragon City Tool and Script instructions in English"""
    return (
        f"{emoji_mgr.diamond} <b>DRAGON CITY TOOL AND SCRIPT</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Access Tools, Scripts and VIP Keys here:</b>\n"
        f"{emoji_mgr.star} <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.warn} <b>Key and VIP Features:</b>\n"
        f"{emoji_mgr.star} Get <b>Free Daily Keys</b> or activate your <b>VIP Key</b> directly.\n"
        f"{emoji_mgr.star} Auto Heroic Race, Quests, Arenas, Chests, and Breed Bot!\n"
        f"{emoji_mgr.warn} <i>Visit the link above to get your key or purchase VIP access!</i>\n\n"
        f"{emoji_mgr.star} <b>To Buy VIP directly:</b> Type <code>/pay</code> or DM {emoji_mgr.vip} :@wolfmodyt {emoji_mgr.vip}"
    )
