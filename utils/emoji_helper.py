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

    @property
    def welcome(self) -> str:
        """Animated megaphone — used to open/close the welcome message."""
        return self.get("welcome", "📢")

    @property
    def fire(self) -> str:
        """Animated fire — used for Dragon VIP feature section headers."""
        return self.get("fire", "🔥")

    @property
    def check(self) -> str:
        """Animated checkmark — used as the bullet for individual features."""
        return self.get("check", "✅")

    @property
    def prohibited(self) -> str:
        """Animated prohibition sign — used for "No ..." group rule bullets."""
        return self.get("prohibited", "🚫")

    @property
    def key(self) -> str:
        """Animated key icon — used where a license key is delivered to the buyer."""
        return self.get("key", "🔑")

    @property
    def choose(self) -> str:
        """Animated pointer icon — used on "Choose a plan/method" prompts."""
        return self.get("choose", "👉")

    @property
    def uid(self) -> str:
        """Animated ID-badge icon — shown before a member's Telegram ID."""
        return self.get("uid", "🆔")


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
        f"{emoji_mgr.fire} <b>Want it instantly?</b> Tap <b>BUY VIP NOW</b> below for automated "
        f"checkout (USDT or bank QR) with your key delivered the moment payment is confirmed.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.diamond} <i>Prefer to pay manually instead? Use any of these:</i>\n\n"
        f"{emoji_mgr.star} <b>PayPal</b> <i>[GLOBAL]</i>\n"
        f"   ├ <code>paypal.me/WolfmodYT197</code>\n"
        f"   └ <code>ledongha2k7@gmail.com</code>\n\n"
        f"{emoji_mgr.star} <b>Binance ID</b> <i>[GLOBAL]</i>\n"
        f"   ├ ID: <code>1158594960</code>\n"
        f"   └ Deposit <i>(BEP20)</i>: <code>0xff924e6b692567a4d9462a3bbef33f48a138dd2e</code>\n\n"
        f"{emoji_mgr.star} <b>SociaBuzz TRIBE</b> <i>[GLOBAL]</i>\n"
        f"   └ <a href=\"https://sociabuzz.com/ldh/tribe\">Tap to open</a>\n\n"
        f"{emoji_mgr.star} <b>Vietcombank</b> <i>[VIETNAM]</i>\n"
        f"   └ <code>9382382864</code> — LE DONG HA\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.warn} <i>Please double-check the details before sending.</i>\n"
        f"{emoji_mgr.warn} <i>PayPal must be sent as <b>Friends &amp; Family</b>.</i>\n"
        f"{emoji_mgr.star} You can also redeem gift codes via <a href=\"https://rewarble.com/\">rewarble.com</a>\n\n"
        f"{emoji_mgr.key} <b>After sending, DM</b> {emoji_mgr.vip} :@wolfmodyt {emoji_mgr.vip} <b>with your proof to confirm.</b>"
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
        f"• Master Admin {emoji_mgr.tele_logo} <b>@wolfmodyt</b> will carefully inspect your evidence and provide assistance as soon as possible.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.star} <b>Direct Admin Contact:</b> @wolfmodyt"
    )

def get_pricing_info_text() -> str:
    """Returns formatted VIP Key Pricing & Subscription details with VIP custom emojis"""
    return (
        f"{emoji_mgr.vip} <b>DRAGON CITY VIP KEY PRICING</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>2 Days VIP Access:</b> <code>$1 USD</code> (1$ / 2 Days)\n"
        f"{emoji_mgr.star} <b>30 Days VIP Access:</b> <code>$7 USD</code> (7$ / 30 Days)\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.diamond} <b>HOW TO PURCHASE VIP:</b>\n"
        f"{emoji_mgr.star} <b>Buy Online:</b> <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n"
        f"{emoji_mgr.star} <b>Payment Methods:</b> Type <code>pay</code> or <code>/pay</code>\n"
        f"{emoji_mgr.star} <b>Direct Purchase via DM:</b> Contact Master Admin {emoji_mgr.tele_logo} :@wolfmodyt {emoji_mgr.tele_logo}"
    )

def get_features_info_text() -> str:
    """Returns beautifully formatted VIP & Free Script detailed feature list"""
    return (
        f"{emoji_mgr.fire} <b>WOLFMOD VIP SCRIPT V9.0 - DRAGON CITY</b> {emoji_mgr.fire}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.vip} <b>VIP FEATURE DETAILED LIST</b> {emoji_mgr.vip}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{emoji_mgr.check} <b>1. APP & MEMORY TOOLS:</b>\n"
        f"{emoji_mgr.check} <b>Revert & Unfreeze Values:</b> Restore original values & unfreeze memory\n"
        f"{emoji_mgr.check} <b>Set Memory Ranges:</b> Configure C_ALLOC + ANONYMOUS ranges\n"
        f"{emoji_mgr.check} <b>Anti Reset Game (Basic):</b> Basic anti-reset / anti-crash protection\n"
        f"{emoji_mgr.check} <b>Hide GameGuardian Icon:</b> Hide GameGuardian floating icon\n"
        f"{emoji_mgr.check} <b>Force Close Game:</b> Immediately force close game\n"
        f"{emoji_mgr.check} <b>Instructions:</b> Detailed usage guide\n\n"
        f"{emoji_mgr.check} <b>2. BATTLE MODS:</b>\n"
        f"{emoji_mgr.check} <b>Easy Arena Battle</b> <i>(also in Free Script)</i>: Auto Win / Auto Lose instantly\n"
        f"{emoji_mgr.check} <b>Easy Leagues Battle:</b> Auto Win / Auto Lose instantly\n"
        f"{emoji_mgr.check} <b>Easy Rescue Battle</b> <i>(also in Free Script)</i>: Auto Win / Auto Lose instantly\n"
        f"{emoji_mgr.check} <b>Easy Quest Battle:</b> Auto Win / Auto Lose instantly\n"
        f"{emoji_mgr.check} <b>Farm Orb:</b> In-battle fixed Orb farming trick\n"
        f"{emoji_mgr.check} <b>Combat / Battle Stats:</b> View Rank, Damage & Health stats for dragons\n\n"
        f"{emoji_mgr.check} <b>3. DRAGON MODS:</b>\n"
        f"{emoji_mgr.check} <b>Hack Max Stats:</b> Max Level, Max Health (God Mode), Max Damage (One-Hit Kill), Max Rank, Max 5 Stars\n"
        f"{emoji_mgr.check} <b>Clone Dragon:</b> Copy appearance & skills to 1 dragon or all dragons\n"
        f"{emoji_mgr.check} <b>Bypass Busy Status:</b> Use dragons while busy (hatching, breeding, training)\n\n"
        f"{emoji_mgr.check} <b>4. TREE OF LIFE MODS:</b>\n"
        f"{emoji_mgr.check} <b>No-Sample Trade:</b> Trade Orbs without owning sample Orbs\n"
        f"{emoji_mgr.check} <b>No-Duplicate Recall:</b> Recall dragons for Orbs without duplicate copies\n\n"
        f"{emoji_mgr.check} <b>5. SKILL HACKS:</b>\n"
        f"{emoji_mgr.check} <b>Bypass Verified Attack Skills:</b> Bypass server-side attack skill verification\n"
        f"{emoji_mgr.check} <b>Train Skill Attack Early:</b> Train skills early at Training Center (No Lv15 required)\n\n"
        f"{emoji_mgr.check} <b>6. TIME & SPEED:</b>\n"
        f"{emoji_mgr.check} <b>Speed Hack Animation:</b> Custom animation & game motion speed hack\n"
        f"{emoji_mgr.check} <b>Skip Time Hatch & Breed:</b> Skip hatching & breeding countdown timers instantly\n\n"
        f"{emoji_mgr.check} <b>7. EVENT MODS & ISLANDS:</b>\n"
        f"{emoji_mgr.check} <b>Skip Event Battle Time:</b> Skip Heroic Race battle cooldown timers instantly\n"
        f"{emoji_mgr.check} <b>Events Data & Analyzer:</b> View Lap/Node data & event reward details\n"
        f"{emoji_mgr.check} <b>Move Habitat & Buildings:</b> Move habitats & buildings freely without limits\n\n"
        f"{emoji_mgr.check} <b>8. EXTRA TOOLS:</b>\n"
        f"{emoji_mgr.check} <b>Complete Item Index:</b> Display complete item index list (<code>tid_</code>)\n"
        f"{emoji_mgr.check} <b>Predict Dragon Collection:</b> Predict dragon collection rewards\n"
        f"{emoji_mgr.check} <b>Offline Mode:</b> Unlock resources, speed up Food\n"
        f"{emoji_mgr.check} <b>Private DNS AdBlocker:</b> Block in-game ads using private DNS\n"
        f"{emoji_mgr.check} <b>Admin Privileges / Commands:</b> Admin commands & quick game restart\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.star} <b>DRAGON CITY FREE SCRIPT FEATURES:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.check} <b>App & GG Tools:</b> Basic configuration\n"
        f"{emoji_mgr.check} <b>Easy Arena Battle:</b> Auto Win / Auto Lose\n"
        f"{emoji_mgr.check} <b>Easy Rescue Battle:</b> Auto Win / Auto Lose\n"
        f"{emoji_mgr.check} <b>Get Free Daily Key:</b> <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.diamond} <b>GET VIP ACCESS & SUPPORT:</b>\n"
        f"{emoji_mgr.check} <b>Buy VIP Key on Web:</b> <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n"
        f"{emoji_mgr.check} <b>VIP Pricing:</b> Type <code>price</code> ($1 / 2 Days, $7 / 30 Days)\n"
        f"{emoji_mgr.check} <b>Payment Methods:</b> Type <code>pay</code> or <code>/pay</code>\n"
        f"{emoji_mgr.check} <b>Website:</b> <a href=\"https://www.wolfmod.xyz\">wolfmod.xyz</a>\n"
        f"{emoji_mgr.check} <b>Facebook:</b> <a href=\"https://fb.com/wolfmodkk\">fb.com/wolfmodkk</a>\n"
        f"{emoji_mgr.check} <b>Telegram Admin:</b> {emoji_mgr.vip} :@wolfmodyt {emoji_mgr.vip}"
    )

