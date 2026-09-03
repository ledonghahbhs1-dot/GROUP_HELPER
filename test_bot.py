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
    def __init__(self, user_id, username, full_name=None):
        self.id = user_id
        self.username = username
        self.full_name = full_name or username

class MockBot:
    pass

async def test():
    print("1. Testing Database init...")
    await db.init_db()
    
    settings = await db.get_chat_settings(-100999999999)
    print("Settings loaded:", settings)
    assert settings["max_warns"] == 5, "Default max_warns must be 5!"
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
    assert emoji_mgr.get("unknown_non_vip_key") == "", "Any icon without a VIP ID must not be used (return empty string)"

    
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

    print("6.5 Testing Issue / Not Working / No Effect Detector (Bilingual)...")
    from filters.issue_filter import issue_detector
    from utils.emoji_helper import get_issue_support_text
    
    assert issue_detector.is_issue_query("sao tool khong hoat dong vay ad?")[0] == True
    assert issue_detector.is_issue_query("script này không có tác dụng gì cả")[0] == True
    assert issue_detector.is_issue_query("the key is not working today")[0] == True
    assert issue_detector.is_issue_query("why is it not work")[0] == True
    assert issue_detector.is_issue_query("tool bị lỗi rồi ad")[0] == True
    assert issue_detector.is_issue_query("k chay dc roi")[0] == True
    assert issue_detector.is_issue_query("it broke and won't work")[0] == True
    assert issue_detector.is_issue_query("hello how are you")[0] == False
    
    issue_text = get_issue_support_text(987654, "Test Member")
    assert "PLEASE PROVIDE VIDEO OR PHOTO PROOF" in issue_text
    assert "@wolfmodyt" in issue_text
    assert "video recording" in issue_text or "screenshot" in issue_text
    print("Issue / Not Working detector tests passed ✅")

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
    
    print("8. Testing Link Filter & Bot Link Detection & Masking...")
    from filters.link_filter import link_filter, mask_link_preview
    from aiogram.types import MessageEntity
    
    class MockLinkMsg:
        def __init__(self, text=None, caption=None, entities=None, caption_entities=None):
            self.text = text
            self.caption = caption
            self.entities = entities or []
            self.caption_entities = caption_entities or []

    # 8.1 Bot link detection & masking (only 3-4 keywords of link shown)
    has_link_bot1, desc_bot1, is_bot1 = await link_filter.check_links(MockLinkMsg(text="Tham gia bot https://t.me/tapswap_bot?start=r_123456789abc nhe"), -100999999999, own_bot_username="my_guard_bot")
    assert has_link_bot1 == True and is_bot1 == True, "Bot URL should be detected as bot link"
    assert "..." in desc_bot1, "Link must be masked with ..."
    assert "r_123456789abc" not in desc_bot1, "Full query parameters must NOT be shown in warning"
    print("Bot link masked preview:", desc_bot1)

    has_link_bot2, desc_bot2, is_bot2 = await link_filter.check_links(MockLinkMsg(text="Nhan token tai @dogshouse_bot"), -100999999999, own_bot_username="my_guard_bot")
    assert has_link_bot2 == True and is_bot2 == True, "Bot mention should be detected as bot link"

    # 8.2 Own bot link should NOT be detected as violation
    has_own_bot, _, _ = await link_filter.check_links(MockLinkMsg(text="Chat voi bot nha @my_guard_bot"), -100999999999, own_bot_username="my_guard_bot")
    assert has_own_bot == False, "Own bot mention should not be flagged"

    # 8.3 General Telegram group link
    has_link1, desc1, is_bot_gen1 = await link_filter.check_links(MockLinkMsg(text="Join my group t.me/somegroup"), -100999999999)
    assert has_link1 == True, "Telegram link should be detected"
    assert "..." in desc1, "General link must also be masked with ..."

    # 8.4 General web URL
    has_link2, desc2, _ = await link_filter.check_links(MockLinkMsg(text="Check this link https://spam-site.xyz/promo/long/path/query"), -100999999999)
    assert has_link2 == True, "Web URL should be detected"
    assert "..." in desc2, "Web URL must be masked"

    # 8.5 Telegram invite link
    has_link3, desc3, _ = await link_filter.check_links(MockLinkMsg(text="Join private invite https://t.me/+AbCdEfGh123"), -100999999999)
    assert has_link3 == True, "Telegram invite + link should be detected"

    # 8.6 Normal message
    has_link4, _, _ = await link_filter.check_links(MockLinkMsg(text="Hello bro how are you"), -100999999999)
    assert has_link4 == False, "Normal message without link should pass"
    print("8.5 Testing Profanity Filter (0 False Positives)...")
    from filters.profanity_filter import profanity_filter
    
    # False positive prevention test cases
    assert (await profanity_filter.check_profanity("Akhnaf Giovanna ࣩࣩࣧࣧࣧࣧࣧࣧࣧࣧࣧࣧࣧࣧ", -100999999999))[0] == False
    assert (await profanity_filter.check_profanity("Chung ta cung di choi nhe", -100999999999))[0] == False
    assert (await profanity_filter.check_profanity("Minh mua 1 lon coca", -100999999999))[0] == False
    assert (await profanity_filter.check_profanity("Xin audio va media", -100999999999))[0] == False
    assert (await profanity_filter.check_profanity("Dieu kien tham gia the nao", -100999999999))[0] == False
    
    # Real profanity detection test cases
    assert (await profanity_filter.check_profanity("con đĩ này", -100999999999))[0] == True
    assert (await profanity_filter.check_profanity("đĩ", -100999999999))[0] == True
    assert (await profanity_filter.check_profanity("duma thang kia", -100999999999))[0] == True
    assert (await profanity_filter.check_profanity("you are a fucking bitch", -100999999999))[0] == True
    print("Profanity filter tests passed (0 false positives) ✅")

    print("9. Testing Scam & Spam Accusation Detection...")
    from filters.scam_filter import scam_detector
    
    is_scam1, kw1 = scam_detector.is_scam_message("thằng này lừa đảo anh em cẩn thận")
    assert is_scam1 == True and ("lừa đảo" in kw1 or "lua dao" in kw1 or "lừa" in kw1)
    
    is_scam2, kw2 = scam_detector.is_scam_message("this guy is a scammer and fraud")
    assert is_scam2 == True and ("scam" in kw2 or "fraud" in kw2)
    
    is_scam3, kw3 = scam_detector.is_scam_message("report thằng này spam bot")
    assert is_scam3 == True and "spam" in kw3
    
    is_scam4, kw4 = scam_detector.is_scam_message("nó bùng tiền của tôi rồi")
    assert is_scam4 == True and ("bùng tiền" in kw4 or "bung tien" in kw4)
    
    is_scam5, _ = scam_detector.is_scam_message("hello admin, how are you today?")
    assert is_scam5 == False
    print("Scam & Spam detection tests passed ✅")
    
    print("10. Testing Welcome Message & Admin Info...")
    from handlers.member_handlers import build_welcome_text, should_welcome
    
    welcome_str = build_welcome_text("Dragon City VIP", 112233, "Nguyen Van A")
    assert "WELCOME TO DRAGON CITY VIP!" in welcome_str
    assert "@wolfmodyt" in welcome_str
    assert "ADMIN & SUPPORT" in welcome_str
    assert "GROUP SECURITY & RULES" in welcome_str
    assert "5 warnings" in welcome_str
    
    assert should_welcome(-100123, 9999) == True
    assert should_welcome(-100123, 9999) == False, "Duplicate welcome within 30s should be prevented"
    print("Welcome message tests passed ✅")
    
    print("11. Testing Target ID Resolution & Admin Command Parser...")
    from handlers.admin_handlers import resolve_target, parse_admin_cmd
    from aiogram.filters import CommandObject
    
    class MockTargetMsg:
        def __init__(self, reply_to_message=None, entities=None, chat=None):
            self.reply_to_message = reply_to_message
            self.entities = entities or []
            self.chat = chat or type("MockChat", (), {"id": -100123456, "type": "supergroup"})()

    class MockRepliedMsg:
        def __init__(self, from_user=None, sender_chat=None):
            self.from_user = from_user
            self.sender_chat = sender_chat

    # Save user into DB cache for @username resolution test
    await db.save_user(111222333, "masteroogwayv1", "Master Oogway")

    # Case 1: ID provided in arguments (/warn 987654321 spam)
    cmd_with_id = CommandObject(prefix="/", command="warn", args="987654321 spamming links")
    t_id1, t_name1, rem1 = await resolve_target(MockTargetMsg(), MockBot(), cmd_with_id)
    assert t_id1 == 987654321
    assert rem1 == "spamming links"

    # Case 2: Plain text command with ID (warn 987654321 spam or ban 987654321)
    t_id1_plain, _, rem1_plain = await resolve_target(MockTargetMsg(), MockBot(), raw_args="987654321 spamming links")
    assert t_id1_plain == 987654321
    assert rem1_plain == "spamming links"

    # Case 3: Username provided in arguments (/unban @masteroogwayv1 and unwarn @masteroogwayv1)
    cmd_unban_user = CommandObject(prefix="/", command="unban", args="@masteroogwayv1")
    t_id_u1, t_name_u1, _ = await resolve_target(MockTargetMsg(), MockBot(), cmd_unban_user)
    assert t_id_u1 == 111222333, f"Expected 111222333, got {t_id_u1}"
    assert "Master Oogway" in t_name_u1

    t_id_u2, t_name_u2, _ = await resolve_target(MockTargetMsg(), MockBot(), raw_args="@masteroogwayv1")
    assert t_id_u2 == 111222333

    # Case 4: ID resolved from reply message (/ban reason)
    cmd_no_args = CommandObject(prefix="/", command="ban", args="rule violation")
    replied_user = MockUser(555666, "badguy")
    t_id2, t_name2, rem2 = await resolve_target(MockTargetMsg(reply_to_message=MockRepliedMsg(from_user=replied_user)), MockBot(), cmd_no_args)
    assert t_id2 == 555666
    assert rem2 == "rule violation"

    # Case 5: No ID provided and no reply -> Must return None
    cmd_empty = CommandObject(prefix="/", command="kick", args="")
    t_id3, _, _ = await resolve_target(MockTargetMsg(), MockBot(), cmd_empty)
    assert t_id3 is None, "Should not resolve target when no ID and no reply"

    # Case 6: Banned Users Database & Username Resolution for already-banned users
    await db.add_banned_user(-100123456, 777888999, "bannedguy", "Banned Guy", "Violated rules")
    banned_list = await db.get_banned_users(-100123456)
    assert any(u["user_id"] == 777888999 for u in banned_list), "Banned user must be in banned_list"
    
    # Resolving already banned user by @username
    t_id_banned, _, _ = await resolve_target(MockTargetMsg(), MockBot(), raw_args="@bannedguy")
    assert t_id_banned == 777888999, f"Expected 777888999 for @bannedguy, got {t_id_banned}"
    
    # Remove from banned list
    await db.remove_banned_user(-100123456, 777888999)
    banned_list_after = await db.get_banned_users(-100123456)
    assert not any(u["user_id"] == 777888999 for u in banned_list_after)

    # Case 7: parse_admin_cmd helper with username, banlist and numeric ID
    assert parse_admin_cmd("warn 123456789 spam", False) == ("warn", "123456789 spam")
    assert parse_admin_cmd("unban @masteroogwayv1", False) == ("unban", "@masteroogwayv1")
    assert parse_admin_cmd("unwarn @masteroogwayv1", False) == ("unwarn", "@masteroogwayv1")
    assert parse_admin_cmd("ban @masteroogwayv1", False) == ("ban", "@masteroogwayv1")
    assert parse_admin_cmd("/unban @masteroogwayv1", False) == ("unban", "@masteroogwayv1")
    assert parse_admin_cmd("/unwarn @masteroogwayv1", False) == ("unwarn", "@masteroogwayv1")
    assert parse_admin_cmd("banlist", False) == ("banlist", "")
    assert parse_admin_cmd("banned", False) == ("banned", "")
    assert parse_admin_cmd("/banlist", False) == ("banlist", "")
    assert parse_admin_cmd("warn", True) == ("warn", "")
    assert parse_admin_cmd("ban", True) == ("ban", "")
    assert parse_admin_cmd("i warn you", False) is None
    assert parse_admin_cmd("pay", False) is None, "'pay' must NOT be parsed as an admin moderation command"

    # Case 8: PlainAdminCommandFilter filter check
    from handlers.admin_handlers import PlainAdminCommandFilter
    class MockFilterMsg:
        def __init__(self, text, reply_to_message=None):
            self.text = text
            self.reply_to_message = reply_to_message

    filter_inst = PlainAdminCommandFilter()
    assert await filter_inst(MockFilterMsg("pay")) == False, "Filter must return False for 'pay' so message falls through to payment detector!"
    assert await filter_inst(MockFilterMsg("warn 123456789")) == {"parsed_admin_cmd": ("warn", "123456789")}
    print("Target ID Resolution, Banned Users Registry & Command Parser tests passed ✅")

    print("\n==========================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS! ✅")
    print("==========================================\n")

if __name__ == "__main__":
    asyncio.run(test())
