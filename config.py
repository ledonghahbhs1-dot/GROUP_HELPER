import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Admin/Owner IDs
raw_owners = os.getenv("OWNER_IDS", "")
OWNER_IDS: List[int] = [
    int(x.strip()) for x in raw_owners.split(",") if x.strip().isdigit()
]

# Whitelist username allowed to message the bot directly in private chat
ALLOWED_PRIVATE_USERNAMES: List[str] = [
    u.strip().lower().lstrip("@")
    for u in os.getenv("ALLOWED_PRIVATE_USERNAMES", "wolfmodyt").split(",")
    if u.strip()
]

# Database Path
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "guard_bot.db"))

# Default Group Settings (Mặc định: Cảnh cáo tối đa 2 lần, quá 2 lần là BAN, tự xoá thông báo sau 30 giây)
DEFAULT_MAX_WARNS: int = int(os.getenv("DEFAULT_MAX_WARNS", 2))
DEFAULT_WARN_ACTION: str = os.getenv("DEFAULT_WARN_ACTION", "ban").lower()  # "ban", "mute", "kick"
DEFAULT_MUTE_DURATION: int = int(os.getenv("DEFAULT_MUTE_DURATION", 3600))  # seconds
AUTO_DELETE_LOGS_SEC: int = int(os.getenv("AUTO_DELETE_LOGS_SEC", 30))       # 30 seconds

# Anti-Spam Sensitivity Config
SPAM_MESSAGE_LIMIT: int = 5        # Max messages
SPAM_INTERVAL_SEC: int = 5         # Within interval (seconds)
SPAM_DUPLICATE_LIMIT: int = 3      # Identical messages in a row
SPAM_DUPLICATE_INTERVAL: int = 30  # Seconds

# Telegram Premium Custom Emoji IDs
# CHỈ DÙNG ID THẬT DO TELEGRAM PREMIUM CUNG CẤP
DEFAULT_EMOJIS: Dict[str, Dict[str, str]] = {
    # 3 Icon Premium thật từ tài khoản người dùng:
    "tele_logo": {"id": os.getenv("EMOJI_TELE_LOGO", "5211129162206560202"), "fallback": "✈️"},
    "clock": {"id": os.getenv("EMOJI_CLOCK", "5382194935057372936"), "fallback": "⏳"},
    "warn": {"id": os.getenv("EMOJI_WARN", "5202101484547766658"), "fallback": "⚠️"},
    
    # Các icon khác mặc định dùng Unicode Emoji đẹp (hoặc cấu hình thêm qua /set_emoji)
    "vip": {"id": os.getenv("EMOJI_VIP", ""), "fallback": "👑"},
    "shield": {"id": os.getenv("EMOJI_SHIELD", "5197288647275071607"), "fallback": "🛡️"},
    "ban": {"id": os.getenv("EMOJI_BAN", ""), "fallback": "🚫"},
    "mute": {"id": os.getenv("EMOJI_MUTE", ""), "fallback": "🔇"},
    "link": {"id": os.getenv("EMOJI_LINK", ""), "fallback": "🔗"},
    "bot": {"id": os.getenv("EMOJI_BOT", ""), "fallback": "🤖"},
    "spam": {"id": os.getenv("EMOJI_SPAM", ""), "fallback": "🔥"},
    "success": {"id": os.getenv("EMOJI_SUCCESS", ""), "fallback": "✅"},
    "error": {"id": os.getenv("EMOJI_ERROR", ""), "fallback": "❌"},
    "settings": {"id": os.getenv("EMOJI_SETTINGS", ""), "fallback": "⚙️"},
    "diamond": {"id": os.getenv("EMOJI_DIAMOND", ""), "fallback": "💎"},
    "star": {"id": os.getenv("EMOJI_STAR", ""), "fallback": "⭐"},
    "lock": {"id": os.getenv("EMOJI_LOCK", ""), "fallback": "🔒"},
    "bell": {"id": os.getenv("EMOJI_BELL", ""), "fallback": "🔔"},
}
