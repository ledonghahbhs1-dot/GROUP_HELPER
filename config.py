import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Admin/Owner IDs (Includes user IDs and Super-Admin Channel/Group IDs)
# @wolfmodyt: 6571486853
raw_owners = os.getenv("OWNER_IDS", "6571486853")
OWNER_IDS: List[int] = [
    int(x.strip()) for x in raw_owners.split(",") if x.strip().lstrip("-").isdigit()
]
# WOLF Team Owner Channel/Sender Chat IDs
OWNER_SENDER_CHAT_IDS: List[int] = [-1002070376940]

# Whitelist username allowed to message the bot directly in private chat
ALLOWED_PRIVATE_USERNAMES: List[str] = [
    u.strip().lower().lstrip("@")
    for u in os.getenv("ALLOWED_PRIVATE_USERNAMES", "wolfmodyt").split(",")
    if u.strip()
]

# Database Path
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "guard_bot.db"))

# Guide video source channel (Telegram posts to forward)
ARENA_VIDEO_CHAT: str = os.getenv("ARENA_VIDEO_CHAT", "@youtubewolfmod")
ARENA_VIDEO_MESSAGE_ID: int = int(os.getenv("ARENA_VIDEO_MESSAGE_ID", 280))  # Arena Battle guide: t.me/youtubewolfmod/280
ORBQUEST_VIDEO_MESSAGE_ID: int = int(os.getenv("ORBQUEST_VIDEO_MESSAGE_ID", 281))  # Farm Orb / Quest / Rank Up guide: t.me/youtubewolfmod/281
MAXSTATS_VIDEO_MESSAGE_ID: int = int(os.getenv("MAXSTATS_VIDEO_MESSAGE_ID", 283))  # Max Health/Damage/Star/Level guide: t.me/youtubewolfmod/283
RECALL_VIDEO_MESSAGE_ID: int = int(os.getenv("RECALL_VIDEO_MESSAGE_ID", 284))  # Force Recall / No-Duplicate Recall guide: t.me/youtubewolfmod/284
HABITAT_VIDEO_MESSAGE_ID: int = int(os.getenv("HABITAT_VIDEO_MESSAGE_ID", 285))  # Move Habitat & Building guide: t.me/youtubewolfmod/285
HEROICRACE_VIDEO_MESSAGE_ID: int = int(os.getenv("HEROICRACE_VIDEO_MESSAGE_ID", 290))  # Skip Heroic Race Battle Time guide: t.me/youtubewolfmod/290
BYPASSVERIFY_VIDEO_MESSAGE_ID: int = int(os.getenv("BYPASSVERIFY_VIDEO_MESSAGE_ID", 295))  # Bypass Verified Skill guide: t.me/youtubewolfmod/295
NOTRADE_VIDEO_MESSAGE_ID: int = int(os.getenv("NOTRADE_VIDEO_MESSAGE_ID", 298))  # Trading Without Sample guide: t.me/youtubewolfmod/298
FREEKEY_VIDEO_MESSAGE_ID: int = int(os.getenv("FREEKEY_VIDEO_MESSAGE_ID", 315))  # How to get Free Key guide: t.me/youtubewolfmod/315

# WolfMod.xyz VIP Key checkout API (live production backend, shared with the website itself)
WOLFMOD_API_BASE_URL: str = os.getenv("WOLFMOD_API_BASE_URL", "https://www.wolfmod.xyz")

# Link4M ad-gate shortener (same token/service as the website's free-key unlock flow).
# Used to wrap the /freescript deep-link so users complete a short ad step before
# the bot delivers the free script. If unset, /freescript falls back to handing
# out the deep link directly (no ad gate).
LINK4M_TOKEN: str = os.getenv("LINK4M_TOKEN", "")

# Direct download links for the Dragon City scripts delivered to buyers/free users.
VIP_SCRIPT_URL: str = os.getenv(
    "VIP_SCRIPT_URL",
    "https://t.me/youtubewolfmod/477",
)
FREE_SCRIPT_URL: str = os.getenv(
    "FREE_SCRIPT_URL",
    "https://t.me/youtubewolfmod/434",
)
PC_TOOL_URL: str = os.getenv(
    "PC_TOOL_URL",
    "https://t.me/youtubewolfmod/492",
)

# Shared secret for POST /api/bot/generate-free-key on the wolfmod.xyz backend
# (that endpoint checks `secret === getSecret()`, i.e. the backend's
# ADMIN_PASSWORD env var). Must be set to that exact same value via Railway/.env
# - deliberately has NO hardcoded default here, since this repo is public and a
# committed real secret would let anyone call that endpoint as the bot.
WOLFMOD_BOT_SECRET: str = os.getenv("WOLFMOD_BOT_SECRET", "")

# Default Group Settings (Mặc định: Cảnh cáo tối đa 5 lần, quá 5 lần là BAN, tự xoá thông báo sau 30 giây)
DEFAULT_MAX_WARNS: int = int(os.getenv("DEFAULT_MAX_WARNS", 5))
DEFAULT_WARN_ACTION: str = os.getenv("DEFAULT_WARN_ACTION", "ban").lower()  # "ban", "mute", "kick"
DEFAULT_MUTE_DURATION: int = int(os.getenv("DEFAULT_MUTE_DURATION", 3600))  # seconds
AUTO_DELETE_LOGS_SEC: int = int(os.getenv("AUTO_DELETE_LOGS_SEC", 30))       # 30 seconds

# Anti-Spam Sensitivity Config
SPAM_MESSAGE_LIMIT: int = 5        # Max messages
SPAM_INTERVAL_SEC: int = 5         # Within interval (seconds)
SPAM_DUPLICATE_LIMIT: int = 3      # Identical messages in a row
SPAM_DUPLICATE_INTERVAL: int = 30  # Seconds

# Telegram Premium Custom Emoji IDs — XÁC MINH HOẠT ĐỘNG 100% TRONG GROUP
VIP_ID    = "5204100216298432738"  # 👑 confirmed group ✅
STAR_ID   = "5202036282649244841"  # ⭐ confirmed group ✅
WARN_ID   = "5213205860498549992"  # ⚠️ confirmed group ✅
TELE_ID   = "5211129162206560202"  # ✈️ confirmed group ✅

# Animated icons (user-supplied, matched against the "GROUP_HELPER" icon board):
# welcome banner (📢, animated), dragon VIP feature headers (🔥, animated),
# and per-feature checkmark bullets (✅, animated).
LOA_ID    = "6154375023462191177"  # 📢 welcome banner
FIRE_ID   = "5424972470023104089"  # 🔥 dragon VIP feature (animated)
CHECK_ID  = "5204236147718387299"  # ✅ feature bullet (animated)
PROHIBITED_ID = "5201841261069236516"  # 🚫 prohibited-rule bullets ("No ...")
DIAMOND_ID = "5202158242540583408"  # 💎 real diamond icon (was reusing VIP_ID before)
KEY_ID = "5201761348907725593"  # 🔑 license key delivered to the buyer
CHOOSE_ID = "5204383160153963970"  # 👉 "Choose a plan/method" prompts
UID_ID = "5778354210110183831"  # 🆔 shown before a member's Telegram ID in the welcome message; also the "Account Name" line on the VietQR payment caption
SALE_ID = "5204311666128350421"  # 🏷️ VIP flash-sale price-drop announcement banner
MONEYBAG_ID = "5213094908608392768"  # 💰 "Amount" line on the VietQR payment caption
BANK_ID = "5332455502917949981"  # 🏦 "Bank" line on the VietQR payment caption; also the "Pay with Bank Transfer" button
CARD_ID = "5445353829304387411"  # 💳 "Account Number" line on the VietQR payment caption; also the "Pay with USDT" button
MEMO_ID = "5395444784611480792"  # 📝 "Transfer Content (required)" line on the VietQR payment caption
CHECKPAID_ID = "5375338737028841420"  # 🔄 "I've Paid - Check Now" button
OPENLINK_ID = "5440410042773824003"  # 🔗 "Open Payment Page" button
BACK_ID = "5393368163628905240"  # ⬅️ "Back" button; also the "Unlock via ..." free-script buttons

# Bot API 9.4+ (Feb 2026) button icons: InlineKeyboardButton.icon_custom_emoji_id
# renders an actual animated/custom emoji ON the button itself (separate from the
# plain-text `text` field, which still needs its own fallback character).
BUYVIP_BUTTON_ICON_ID = "5203915043078436374"  # shown on the "BUY VIP NOW" button
VIP_SCRIPT_BUTTON_ICON_ID = "5202132945183208703"  # shown on the "Download VIP Script" button
PC_TOOL_BUTTON_ICON_ID = "5202132945183208703"  # shown on the "Download Tool PC" button (VIP icon)
FREE_SCRIPT_BUTTON_ICON_ID = "5204334519649335950"  # shown on the "Download Free Script" button
FREE_SCRIPT_ID = "5204334519649335950"  # 🎁 custom VIP emoji for Free Script

TOOL_TITLE_ID = "5201906965478930360"  # 👑 crown title icon (items 1 & 2)
TOOL_ACCESS_ID = "5224450179368767019"  # 🌐 tool access icon (item 3)
DOWNLOAD_HEADER_ID = "5201778223834257724"  # 🔥 download script links header icon (item 5)
FEATURES_HEADER_ID = "5204128919564875264"  # 💎 key and vip features header icon (item 6)
DAILY_KEY_BULLET_ID = "5202132945183208703"  # 🚀 daily free key bullet icon (item 7)
AUTOMATION_BULLET_ID = "5420094143089111506"  # 🤖 auto heroic race/arenas bot icon (item 8)
DOWNLOAD_PROMPT_ID = "5416028144794617466"  # 📥 visit links/download prompt icon (item 9)

# Payment Methods (/pay) Custom Emoji IDs (Part 2)
PAY_TITLE_ID = "5201906965478930360"  # 👑 payment title (items 1 & 2)
PAY_INSTANT_ID = "5201778223834257724"  # 🔥 want it instantly (item 3)
PAY_MANUAL_ID = "5202132945183208703"  # 💎 prefer to pay manually (item 4)
PAY_PAYPAL_ID = "5393614626032217242"  # 💵 PayPal (item 5)
PAY_BINANCE_ID = "5379773896352355687"  # 🪙 Binance ID (item 6)
PAY_SOCIABUZZ_ID = "5366471686851933528"  # ☕ SociaBuzz TRIBE (item 7)
PAY_VCB_ID = "5204242830687494041"  # 🏦 Vietcombank (item 8)
PAY_CHECK_NOTE_ID = "5202101484547766658"  # ⚠️ double-check details note (item 9)
PAY_FF_NOTE_ID = "5420323339723881652"  # ⚠️ PayPal friends & family note (item 10)
PAY_GIFT_NOTE_ID = "6217550861355192234"  # 🎁 rewarble gift codes note (item 11)
PAY_CONFIRM_KEY_ID = "5420094143089111506"  # 🔑 after sending DM note (item 12)
PAY_CONFIRM_VIP_ID = "5204096174734207869"  # 👑 crown in DM :@wolfmodyt (item 13)

# VIP Key Pricing (/price) Custom Emoji IDs (Part 1)
PRICE_TITLE_ID = "5201906965478930360"  # 👑 price title (items 1 & 2)
PRICE_2DAYS_ID = "5393178605247296631"  # ⏳ 2 days access (item 3)
PRICE_30DAYS_ID = "5202132945183208703"  # 💎 30 days access (item 4)
PRICE_HOW_TO_ID = "5312361253610475399"  # 🛒 how to purchase header (item 5)
PRICE_ONLINE_ID = "5447410659077661506"  # 🌐 buy online link (item 6)
PRICE_PAY_METHOD_ID = "5445353829304387411"  # 💳 payment methods (item 7)
PRICE_DM_ID = "5253742260054409879"  # 📩 direct purchase via DM (item 8)
PRICE_ADMIN_ID = "5208416409322799176"  # ✈️ / Admin badge in DM (item 9)

DEFAULT_EMOJIS: Dict[str, Dict[str, str]] = {
    "tele_logo": {"id": TELE_ID, "fallback": "✈️"},
    "clock":     {"id": WARN_ID, "fallback": "⚠️"},
    "warn":      {"id": WARN_ID, "fallback": "⚠️"},
    "vip":       {"id": VIP_ID,  "fallback": "👑"},
    "shield":    {"id": WARN_ID, "fallback": "⚠️"},
    "ban":       {"id": WARN_ID, "fallback": "⚠️"},
    "mute":      {"id": WARN_ID, "fallback": "⚠️"},
    "link":      {"id": STAR_ID, "fallback": "⭐"},
    "bot":       {"id": WARN_ID, "fallback": "⚠️"},
    "spam":      {"id": WARN_ID, "fallback": "⚠️"},
    "success":   {"id": STAR_ID, "fallback": "⭐"},
    "error":     {"id": WARN_ID, "fallback": "⚠️"},
    "settings":  {"id": STAR_ID, "fallback": "⭐"},
    "setting":   {"id": STAR_ID, "fallback": "⭐"},
    "diamond":   {"id": DIAMOND_ID, "fallback": "💎"},
    "star":      {"id": STAR_ID, "fallback": "⭐"},
    "lock":      {"id": WARN_ID, "fallback": "⚠️"},
    "bell":      {"id": STAR_ID, "fallback": "⭐"},
    "welcome":   {"id": LOA_ID,   "fallback": "📢"},
    "fire":      {"id": FIRE_ID,  "fallback": "🔥"},
    "check":     {"id": CHECK_ID, "fallback": "✅"},
    "prohibited": {"id": PROHIBITED_ID, "fallback": "🚫"},
    "key":       {"id": KEY_ID, "fallback": "🔑"},
    "choose":    {"id": CHOOSE_ID, "fallback": "👉"},
    "uid":       {"id": UID_ID, "fallback": "🆔"},
    "sale":      {"id": SALE_ID, "fallback": "🏷️"},
    "moneybag":  {"id": MONEYBAG_ID, "fallback": "💰"},
    "bank":      {"id": BANK_ID, "fallback": "🏦"},
    "card":      {"id": CARD_ID, "fallback": "💳"},
    "memo":      {"id": MEMO_ID, "fallback": "📝"},
    "openlink":  {"id": OPENLINK_ID, "fallback": "🔗"},
    "free_script": {"id": FREE_SCRIPT_ID, "fallback": "🎁"},
    "tool_title":        {"id": TOOL_TITLE_ID, "fallback": "👑"},
    "tool_access":       {"id": TOOL_ACCESS_ID, "fallback": "🌐"},
    "download_header":   {"id": DOWNLOAD_HEADER_ID, "fallback": "🔥"},
    "features_header":   {"id": FEATURES_HEADER_ID, "fallback": "💎"},
    "daily_key_bullet":  {"id": DAILY_KEY_BULLET_ID, "fallback": "🚀"},
    "automation_bullet": {"id": AUTOMATION_BULLET_ID, "fallback": "🤖"},
    "download_prompt":   {"id": DOWNLOAD_PROMPT_ID, "fallback": "📥"},
    "pay_title":         {"id": PAY_TITLE_ID, "fallback": "👑"},
    "pay_instant":       {"id": PAY_INSTANT_ID, "fallback": "🔥"},
    "pay_manual":        {"id": PAY_MANUAL_ID, "fallback": "💎"},
    "pay_paypal":        {"id": PAY_PAYPAL_ID, "fallback": "💵"},
    "pay_binance":       {"id": PAY_BINANCE_ID, "fallback": "🪙"},
    "pay_sociabuzz":     {"id": PAY_SOCIABUZZ_ID, "fallback": "☕"},
    "pay_vcb":           {"id": PAY_VCB_ID, "fallback": "🏦"},
    "pay_check_note":    {"id": PAY_CHECK_NOTE_ID, "fallback": "⚠️"},
    "pay_ff_note":       {"id": PAY_FF_NOTE_ID, "fallback": "⚠️"},
    "pay_gift_note":     {"id": PAY_GIFT_NOTE_ID, "fallback": "🎁"},
    "pay_confirm_key":   {"id": PAY_CONFIRM_KEY_ID, "fallback": "🔑"},
    "pay_confirm_vip":   {"id": PAY_CONFIRM_VIP_ID, "fallback": "👑"},
    "price_title":       {"id": PRICE_TITLE_ID, "fallback": "👑"},
    "price_2days":       {"id": PRICE_2DAYS_ID, "fallback": "⏳"},
    "price_30days":      {"id": PRICE_30DAYS_ID, "fallback": "💎"},
    "price_how_to":      {"id": PRICE_HOW_TO_ID, "fallback": "🛒"},
    "price_online":      {"id": PRICE_ONLINE_ID, "fallback": "🌐"},
    "price_pay_method":  {"id": PRICE_PAY_METHOD_ID, "fallback": "💳"},
    "price_dm":          {"id": PRICE_DM_ID, "fallback": "📩"},
    "price_admin":       {"id": PRICE_ADMIN_ID, "fallback": "👑"},
}




