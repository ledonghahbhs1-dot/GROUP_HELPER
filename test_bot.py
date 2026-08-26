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
from utils.auth import is_user_allowed_private, is_admin_or_owner
from filters.spam_filter import spam_filter
from filters.profanity_filter import profanity_filter
from filters.link_filter import link_filter

class MockUser:
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

class MockBot:
    pass

async def test():
    print("1. Testing Database init...")
    await db.init_db()
    
    settings = await db.get_chat_settings(-100999999999)
    print("Settings loaded:", settings)
    assert settings["max_warns"] == 2, "Default max_warns must be 2!"
    assert settings["warn_action"] == "ban", "Default warn_action must be ban!"
    
    print("2. Testing Master Auth for @wolfmodyt...")
    user_wolfmod = MockUser(12345, "wolfmodyt")
    user_wolfmod_caps = MockUser(12345, "WolfModYT")
    user_stranger = MockUser(67890, "stranger_guy")
    
    bot = MockBot()
    assert await is_admin_or_owner(-100123456, user_wolfmod, bot) == True, "@wolfmodyt must have master admin access everywhere!"
    assert await is_admin_or_owner(0, user_wolfmod, bot) == True, "@wolfmodyt must have access in private chat!"
    assert is_user_allowed_private(user_wolfmod_caps) == True, "@WolfModYT must be allowed!"
    assert is_user_allowed_private(user_stranger) == False, "Strangers must be denied in private!"
    print("Auth tests passed ✅")
    
    print("3. Testing Custom Emojis...")
    await emoji_mgr.load_emojis()
    sig = emoji_mgr.signature
    print("Signature:", repr(sig))
    assert "5211129162206560202" in sig or "wolfmodyt" in sig
    assert "5213205860498549992" in emoji_mgr.clock
    assert "5213205860498549992" in emoji_mgr.warn

    
    print("4. Testing Emoji Fallback Stripper...")
    raw_html = '<tg-emoji emoji-id="12345">👑</tg-emoji> Hello <tg-emoji emoji-id="67890">⚠️</tg-emoji>'
    clean_html = emoji_mgr.strip_tg_emojis(raw_html)
    print("Stripped fallback:", clean_html)
    assert clean_html == "👑 Hello ⚠️", "Fallback stripping failed!"
    
    print("5. Testing Payment Detection (Bilingual)...")
    from filters.payment_filter import payment_detector
    from utils.emoji_helper import get_payment_info_text
    
    assert payment_detector.is_payment_query("pay") == True
    assert payment_detector.is_payment_query("how to pay?") == True
    assert payment_detector.is_payment_query("xin stk chuyen khoan") == True
    assert payment_detector.is_payment_query("cho minh xin gia vip voi") == True
    assert payment_detector.is_payment_query("thanh toan the nao") == True
    assert payment_detector.is_payment_query("paypal me") == True
    assert payment_detector.is_payment_query("vcb le dong ha") == True
    assert payment_detector.is_payment_query("rewarble code") == True
    assert payment_detector.is_payment_query("hello good morning") == False
    
    pay_text = get_payment_info_text()
    assert "paypal.me/WolfmodYT197" in pay_text
    assert "9382382864" in pay_text
    assert "rewarble.com" in pay_text
    assert "PAYMENT METHODS" in pay_text
    print("6. Testing Script & Tool Detection (Bilingual)...")
    from filters.script_filter import script_detector
    from utils.emoji_helper import get_script_tool_info_text
    
    assert script_detector.is_script_query("script") == True
    assert script_detector.is_script_query("tool") == True
    assert script_detector.is_script_query("dragon city tool") == True
    assert script_detector.is_script_query("how to get vip key?") == True
    assert script_detector.is_script_query("cho xin key free voi") == True
    assert script_detector.is_script_query("lay key dc o dau") == True
    assert script_detector.is_script_query("wolfmod dragon city") == True
    assert script_detector.is_script_query("hello how are you") == False
    
    script_text = get_script_tool_info_text()
    assert "wolfmod.xyz/dragon-city" in script_text
    assert "DRAGON CITY TOOL AND SCRIPT" in script_text
    print("Script detector tests passed ✅")

    print("7. Testing Bot Forward Detection...")
    from handlers.message_handlers import check_bot_forward
    from aiogram.types import MessageOriginUser, User
    
    bot_origin = MessageOriginUser(type="user", date=12345, sender_user=User(id=999, is_bot=True, first_name="SpamBot", username="spambot"))
    human_origin = MessageOriginUser(type="user", date=12345, sender_user=User(id=888, is_bot=False, first_name="RealHuman", username="human"))
    
    class MockMsg:
        def __init__(self, forward_origin=None, forward_from=None, via_bot=None):
            self.forward_origin = forward_origin
            self.forward_from = forward_from
            self.via_bot = via_bot
    
    is_fwd_bot, desc1 = check_bot_forward(MockMsg(forward_origin=bot_origin))
    assert is_fwd_bot == True, "Bot origin should be detected"
    assert "@spambot" in desc1

    is_fwd_human, _ = check_bot_forward(MockMsg(forward_origin=human_origin))
    assert is_fwd_human == False, "Human origin should not be detected as bot"

    is_via_bot, desc2 = check_bot_forward(MockMsg(via_bot=User(id=777, is_bot=True, first_name="InlineBot", username="inline_bot")))
    assert is_via_bot == True, "Inline bot should be detected"
    assert "@inline_bot" in desc2
    print("Bot forward tests passed ✅")
    
    print("8. Testing Link Filter...")
    from filters.link_filter import link_filter
    from aiogram.types import MessageEntity
    
    class MockLinkMsg:
        def __init__(self, text=None, caption=None, entities=None, caption_entities=None):
            self.text = text
            self.caption = caption
            self.entities = entities or []
            self.caption_entities = caption_entities or []

    has_link1, desc1 = await link_filter.check_links(MockLinkMsg(text="Join my group t.me/somegroup"), -100999999999)
    assert has_link1 == True, "Telegram link should be detected"

    has_link2, desc2 = await link_filter.check_links(MockLinkMsg(text="Check this link https://spam-site.xyz/promo"), -100999999999)
    assert has_link2 == True, "Web URL should be detected"

    has_link3, desc3 = await link_filter.check_links(MockLinkMsg(text="Join private invite https://t.me/+AbCdEfGh123"), -100999999999)
    assert has_link3 == True, "Telegram invite + link should be detected"

    has_link4, _ = await link_filter.check_links(MockLinkMsg(text="Hello bro how are you"), -100999999999)
    assert has_link4 == False, "Normal message without link should pass"
    print("Link filter tests passed ✅")

    print("\n==========================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS! ✅")
    print("==========================================\n")

if __name__ == "__main__":
    asyncio.run(test())
