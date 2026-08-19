import asyncio
import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from database.db import db
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters
from utils.emoji_helper import emoji_mgr
from filters.spam_filter import spam_filter
from filters.profanity_filter import profanity_filter
from filters.link_filter import link_filter
from handlers.message_handlers import is_user_allowed_private

class MockUser:
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

async def test():
    print("1. Testing Database init...")
    await db.init_db()
    
    settings = await db.get_chat_settings(-100999999999)
    print("Settings loaded:", settings)
    assert settings["max_warns"] == 2, "Default max_warns must be 2!"
    assert settings["warn_action"] == "ban", "Default warn_action must be ban!"
    assert config.AUTO_DELETE_LOGS_SEC == 30, "Auto delete must be 30s!"
    
    print("2. Testing Private Chat Whitelist for @wolfmodyt...")
    user_wolfmod = MockUser(12345, "wolfmodyt")
    user_wolfmod_caps = MockUser(12345, "WolfModYT")
    user_stranger = MockUser(67890, "stranger_guy")
    user_none = MockUser(11111, None)
    
    assert is_user_allowed_private(user_wolfmod) == True, "@wolfmodyt should be allowed!"
    assert is_user_allowed_private(user_wolfmod_caps) == True, "@WolfModYT (case insensitive) should be allowed!"
    assert is_user_allowed_private(user_stranger) == False, "Strangers must be ignored!"
    assert is_user_allowed_private(user_none) == False, "No username must be ignored!"
    print("Whitelist test passed ✅")
    
    print("3. Testing Custom Emojis & Signature...")
    await emoji_mgr.load_emojis()
    sig = emoji_mgr.signature
    print("Signature:", repr(sig))
    assert "5211129162206560202" in sig or "wolfmodyt" in sig, "Signature must contain Telegram icon and @wolfmodyt!"
    assert "5382194935057372936" in emoji_mgr.clock, "Clock must contain custom ID 5382194935057372936!"
    print("Clock emoji tag:", repr(emoji_mgr.clock))
    
    formatted_msg = emoji_mgr.format_msg("Hello test message")
    print("Formatted message sample:\n", formatted_msg)
    assert ":@wolfmodyt" in formatted_msg, "Formatted message must end with signature!"
    
    print("4. Testing Profanity Filter...")
    is_bad, bad_word = await profanity_filter.check_profanity("Mày là đồ óc chó", -100999999999)
    assert is_bad == True, "Profanity detection failed!"
    
    print("5. Testing Spam Filter...")
    user_id = 88888
    chat_id = -100999999999
    for i in range(4):
        spam_filter.check_spam(chat_id, user_id, f"spam test {i}")
    spam_filter.check_spam(chat_id, user_id, "spam test 5")
    is_sp_final, desc_final = spam_filter.check_spam(chat_id, user_id, "spam test 6")
    assert is_sp_final == True, "Spam detection failed!"
    
    print("\n==========================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS! ✅")
    print("==========================================\n")

if __name__ == "__main__":
    asyncio.run(test())
