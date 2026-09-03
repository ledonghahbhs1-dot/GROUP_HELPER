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
        """Forces the bot to use hardcoded safe config emojis to prevent DOCUMENT_INVALID bugs"""
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

        if emoji_id and emoji_id.isdigit():
            return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

        # Icon nào không có ID VIP thì không dùng (trả về chuỗi rỗng)
        return ""

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

    # Convenient VIP Emoji methods — fallback chars: only ⭐ ⚠️ 👑 ✈️ confirmed safe in groups
    @property
    def vip(self) -> str:
        return self.get("vip", "👑")

    @property
    def shield(self) -> str:
        return self.get("shield", "⚠️")   # safe fallback

    @property
    def warn(self) -> str:
        return self.get("warn", "⚠️")

    @property
    def ban(self) -> str:
        return self.get("ban", "⚠️")      # safe fallback

    @property
    def mute(self) -> str:
        return self.get("mute", "⚠️")     # safe fallback

    @property
    def link(self) -> str:
        return self.get("link", "⭐")      # safe fallback

    @property
    def bot(self) -> str:
        return self.get("bot", "⚠️")      # safe fallback

    @property
    def spam(self) -> str:
        return self.get("spam", "⚠️")     # safe fallback

    @property
    def success(self) -> str:
        return self.get("success", "⭐")   # safe fallback

    @property
    def error(self) -> str:
        return self.get("error", "⚠️")    # safe fallback

    @property
    def settings(self) -> str:
        return self.get("settings", "⭐")  # safe fallback

    @property
    def diamond(self) -> str:
        return self.get("diamond", "⭐")   # ⭐ safe — 💎 causes DOCUMENT_INVALID

    @property
    def star(self) -> str:
        return self.get("star", "⭐")

    @property
    def lock(self) -> str:
        return self.get("lock", "⚠️")     # safe fallback

    @property
    def bell(self) -> str:
        return self.get("bell", "⭐")      # safe fallback

    @property
    def admin(self) -> str:
        """Returns VIP Crown icon for Administrators"""
        return self.get("vip", "👑")


from utils.logger import logger

emoji_mgr = EmojiManager()

async def _try_send_stripping_bad_emojis(send_fn, text: str, **kwargs):
    """
    Attempts to send `text`. If Telegram rejects it (e.g. DOCUMENT_INVALID, bad entities, boost required),
    falls back cleanly to stripped standard emojis, and then plain text.
    """
    try:
        return await send_fn(text, **kwargs)
    except TelegramBadRequest as e:
        logger.warning("TelegramBadRequest sending formatted text (%s) — falling back to plain HTML", e)
        plain_text = emoji_mgr.strip_tg_emojis(text)
        try:
            return await send_fn(plain_text, **kwargs)
        except TelegramBadRequest as e2:
            logger.error("Failed to send stripped HTML: %s — falling back to raw text", e2)
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "parse_mode"}
            raw_text = re.sub(r'<[^>]+>', '', plain_text)
            try:
                return await send_fn(raw_text, **clean_kwargs)
            except Exception as e3:
                logger.error("Final send failure: %s", e3)
                return None

async def safe_answer(message, text: str, delay_sec: int = 0, **kwargs):
    """Helper to reply to a message safely handling tg-emoji tags with auto-retry and auto-delete"""
    msg = None
    try:
        msg = await _try_send_stripping_bad_emojis(message.answer, text, **kwargs)
    except Exception as e:
        logger.error(f"Error in safe_answer: {e}")
        try:
            msg = await message.answer(emoji_mgr.strip_tg_emojis(text), parse_mode="HTML", **kwargs)
        except Exception:
            pass

    if msg and delay_sec > 0:
        import asyncio
        asyncio.create_task(_delayed_delete(msg, delay_sec))
    return msg

async def safe_send_message(bot, chat_id: int, text: str, delay_sec: int = 0, **kwargs):
    """Helper to send a message to a chat safely handling tg-emoji tags with auto-retry and auto-delete"""
    msg = None
    try:
        async def _sender(t, **kw):
            return await bot.send_message(chat_id=chat_id, text=t, **kw)
        msg = await _try_send_stripping_bad_emojis(_sender, text, **kwargs)
    except Exception as e:
        logger.error(f"Error in safe_send_message: {e}")
        try:
            msg = await bot.send_message(chat_id=chat_id, text=emoji_mgr.strip_tg_emojis(text), parse_mode="HTML", **kwargs)
        except Exception:
            pass

    if msg and delay_sec > 0:
        import asyncio
        asyncio.create_task(_delayed_delete(msg, delay_sec))
    return msg

async def _delayed_delete(msg, delay_sec: int):
    import asyncio
    await asyncio.sleep(delay_sec)
    try:
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
        f"{emoji_mgr.vip} <b>PAYMENT METHODS</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>PayPal [GLOBAL]:</b> <code>paypal.me/WolfmodYT197</code>\n"
        f"   └ <b>GMAIL PAYPAL:</b> <code>ledongha2k7@gmail.com</code>\n\n"
        f"{emoji_mgr.star} <b>Binance ID [GLOBAL]:</b> <code>1158594960</code>\n"
        f"   └ <b>Deposit Address:</b> <code>0xff924e6b692567a4d9462a3bbef33f48a138dd2e</code> (network bep20)\n\n"
        f"{emoji_mgr.star} <b>SociaBuzz TRIBE:</b> <a href=\"https://sociabuzz.com/ldh/tribe\">LINK</a>\n\n"
        f"{emoji_mgr.star} <b>VCB (Vietcombank) [VIETNAM]:</b> <code>9382382864</code> | <b>LE DONG HA</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.warn} <i>Please send the correct information.</i>\n"
        f"{emoji_mgr.warn} <i>Please send by <b>FRIENDS AND FAMILY OPTION</b> !</i>\n"
        f"{emoji_mgr.star} <b>Note:</b> You can also redeem codes via <a href=\"https://rewarble.com/\">rewarble.com</a>\n\n"
        f"{emoji_mgr.star} <b>After sending, please DM</b> {emoji_mgr.vip} :@wolfmodyt {emoji_mgr.vip} <b>to confirm.</b>"
    )

def get_script_tool_info_text() -> str:
    """Returns formatted VIP Dragon City Tool and Script instructions in English"""
    return (
        f"{emoji_mgr.vip} <b>DRAGON CITY TOOL AND SCRIPT</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Access Tools, Scripts and VIP Keys here:</b>\n"
        f"{emoji_mgr.star} <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.warn} <b>Key and VIP Features:</b>\n"
        f"{emoji_mgr.star} Get <b>Free Daily Keys</b> or activate your <b>VIP Key</b> directly.\n"
        f"{emoji_mgr.star} Auto Heroic Race, Quests, Arenas, Chests, and Breed Bot!\n"
        f"{emoji_mgr.warn} <i>Visit the link above to get your key or purchase VIP access!</i>\n\n"
        f"{emoji_mgr.star} <b>To Buy VIP directly:</b> Type <code>/pay</code> or DM {emoji_mgr.vip} :@wolfmodyt {emoji_mgr.vip}"
    )

def get_issue_support_text(user_id: int = 0, user_name: str = "") -> str:
    """Returns formatted English support message requesting video or photo evidence for not-working/issue reports"""
    user_line = ""
    if user_id and user_name:
        user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
        user_line = f"{emoji_mgr.star} <b>Reported by:</b> {user_mention} (<code>{user_id}</code>)\n\n"
    elif user_id:
        user_line = f"{emoji_mgr.star} <b>User ID:</b> <code>{user_id}</code>\n\n"

    return (
        f"{emoji_mgr.shield} <b>TECHNICAL SUPPORT & ISSUE ASSISTANCE</b> {emoji_mgr.vip}\n\n"
        f"{user_line}"
        f"{emoji_mgr.warn} <b>Issue Notice:</b> <i>If the tool, script, or key is not working / has no effect:</i>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.star} <b>PLEASE PROVIDE VIDEO OR PHOTO PROOF:</b>\n"
        f"• Please reply with a <b>video recording</b> or <b>screenshot / photos</b> demonstrating the problem.\n"
        f"• Make sure to capture any error code, console log, or the exact behavior occurring.\n\n"
        f"{emoji_mgr.diamond} <b>ADMIN REVIEW:</b>\n"
        f"• Master Admin {emoji_mgr.vip} <b>@wolfmodyt</b> will carefully inspect your evidence and provide assistance as soon as possible.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.star} <b>Direct Admin Contact:</b> @wolfmodyt"
    )

