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
    "https://www.mediafire.com/file/7ktpiduqz94naxk/%255BDragonCity_V9.1_VIP%255D_%25283%2529.lua/file",
)
FREE_SCRIPT_URL: str = os.getenv(
    "FREE_SCRIPT_URL",
    "https://www.mediafire.com/file/xyyl50kklt3g142/[DragonCity_2.0_FREE_ALL_SERVER.lua+(3).lua/file",
)

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
}




