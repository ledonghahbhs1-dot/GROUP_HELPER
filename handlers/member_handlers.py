import asyncio
import html
import random
import time
from typing import Dict, Tuple, Any
from aiogram import Router, F, Bot
from aiogram.types import ChatMemberUpdated, Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, KICKED, LEFT, RESTRICTED
from database.db import db
from utils.emoji_helper import emoji_mgr, safe_send_message, safe_answer, schedule_auto_delete
from utils.auth import is_admin_or_owner
from utils.logger import logger
import config

router = Router(name="member_handlers")

# The 8 major VIP feature categories (matches get_features_info_text() section headers)
VIP_FEATURE_CATEGORIES = [
    ("🛠", "App & Memory Tools"),
    ("🗡️", "Battle Mods"),
    ("🐉", "Dragon Mods"),
    ("🌳", "Tree of Life Mods"),
    ("🔱", "Skill Hacks"),
    ("⏱️", "Time & Speed"),
    ("🎪", "Event Mods & Islands"),
    ("📦", "Extra Tools"),
]

# Prevent duplicate welcome messages for same user within 30s
_welcomed_users = {}

# Active captcha verification challenges: (chat_id, user_id) -> dict
_pending_captchas: Dict[Tuple[int, int], Dict[str, Any]] = {}

# Rate limit for initiating captcha challenge: (chat_id, user_id) -> float
_captcha_started: Dict[Tuple[int, int], float] = {}

def should_start_captcha(chat_id: int, user_id: int) -> bool:
    now = time.time()
    expired = [k for k, v in _captcha_started.items() if now - v > 300]
    for k in expired:
        _captcha_started.pop(k, None)

    last_time = _captcha_started.get((chat_id, user_id), 0)
    if now - last_time < 30:
        return False
    _captcha_started[(chat_id, user_id)] = now
    return True

def is_pending_captcha(chat_id: int, user_id: int) -> bool:
    """Returns True if user has an unresolved captcha challenge in progress"""
    if (chat_id, user_id) in _pending_captchas:
        data = _pending_captchas[(chat_id, user_id)]
        if time.time() - data.get("created_at", 0) > 300:
            _pending_captchas.pop((chat_id, user_id), None)
            return False
        return True
    return False

def clear_pending_captcha(chat_id: int, user_id: int):
    """Clears pending captcha state for a user (e.g. when unmuted/unbanned by admin)"""
    _pending_captchas.pop((chat_id, user_id), None)
    _captcha_started.pop((chat_id, user_id), None)

def should_welcome(chat_id: int, user_id: int) -> bool:
    now = time.time()
    # Expire old records (> 5 mins)
    expired = [k for k, v in _welcomed_users.items() if now - v > 300]
    for k in expired:
        _welcomed_users.pop(k, None)

    last_time = _welcomed_users.get((chat_id, user_id), 0)
    if now - last_time < 30:
        return False
    _welcomed_users[(chat_id, user_id)] = now
    return True

def build_welcome_text(chat_title: str, user_id: int, user_name: str) -> str:
    """Build English VIP welcome message with Admin info and Group rules using VIP custom emojis"""
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
    group_name = html.escape(chat_title or "OUR GROUP")
    text = (
        f"{emoji_mgr.welcome} <b>WELCOME TO {group_name.upper()}!</b> {emoji_mgr.welcome}\n\n"
        f"{emoji_mgr.star} <b>Welcome member:</b> {user_mention}\n"
        f"{emoji_mgr.uid} <code>{user_id}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.shield} <b>ADMIN & SUPPORT CONTACT:</b>\n"
        f"• {emoji_mgr.tele_logo} <b>Owner / Master Admin:</b> @wolfmodyt {emoji_mgr.tele_logo}\n"
        f"• {emoji_mgr.star} <b>Payment Methods (VIP Key):</b> Type <code>pay</code> in chat or DM {emoji_mgr.vip} :@wolfmodyt\n"
        f"• {emoji_mgr.star} <b>Dragon City Tool & Script:</b> Type <code>tool</code> or <code>script</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.fire} <b>DRAGON CITY VIP FEATURES</b> {emoji_mgr.fire}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        # Buttons below keep each category's own plain emoji (Telegram buttons
        # can't render animated <tg-emoji>); the message body uses the
        # animated check icon uniformly per the user's request.
        + "".join(f"{emoji_mgr.check} {name}\n" for _icon, name in VIP_FEATURE_CATEGORIES)
        + f"\n{emoji_mgr.star} <i>Tap a category below to unlock it with VIP!</i>\n\n"
        f"{emoji_mgr.warn} <b>GROUP SECURITY & RULES:</b>\n"
        f"• {emoji_mgr.prohibited} No spamming or excessive flood messages\n"
        f"• {emoji_mgr.prohibited} No unauthorized links / Telegram invite links\n"
        f"• {emoji_mgr.prohibited} No forwarded messages from bots / inline bots\n"
        f"• {emoji_mgr.warn} <i>Violators will receive warnings (5 warnings = PERMANENT BAN).</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.diamond} <i>Wishing you a wonderful experience!</i>"
    )
    return emoji_mgr.format_msg(text)

async def build_buyvip_keyboard(bot: Bot, chat_type: str = "private") -> InlineKeyboardMarkup:
    """Shared "BUY VIP NOW" button used on the welcome message, the feature
    list, the buy-vip keyword reply, and the payment-info reply — kept in one
    place so all four stay in sync.
    In a group, this is a t.me deep-link URL that switches the user into a
    private chat with the bot (payment/plan details should never sit in a
    group). In a private chat it's a plain callback that reveals the VIP plan
    menu immediately, since there's no group to leak into.
    icon_custom_emoji_id (Bot API 9.4+) puts an actual animated icon on the
    button itself; "BUY VIP NOW" stays as plain text since the button `text`
    field still can't carry a <tg-emoji> tag."""
    if chat_type == "private":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="BUY VIP NOW", callback_data="show_buyvip_menu",
                icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
            )]
        ])
    bot_info = await bot.get_me()
    buyvip_url = f"https://t.me/{bot_info.username}?start=buyvip"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="BUY VIP NOW", url=buyvip_url,
            icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
        )]
    ])

async def build_vip_script_keyboard(bot: Bot, chat_type: str = "group") -> InlineKeyboardMarkup:
    """Builds inline keyboard with direct download button for VIP Script (https://t.me/youtubewolfmod/477)"""
    download_btn = InlineKeyboardButton(
        text="Download VIP Script",
        url=config.VIP_SCRIPT_URL,
        icon_custom_emoji_id=config.VIP_SCRIPT_BUTTON_ICON_ID,
    )
    if chat_type == "private":
        buy_btn = InlineKeyboardButton(
            text="BUY VIP NOW", callback_data="show_buyvip_menu",
            icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
        )
    else:
        bot_info = await bot.get_me()
        buyvip_url = f"https://t.me/{bot_info.username}?start=buyvip"
        buy_btn = InlineKeyboardButton(
            text="BUY VIP NOW", url=buyvip_url,
            icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
        )
    return InlineKeyboardMarkup(inline_keyboard=[[download_btn], [buy_btn]])

async def build_free_script_keyboard(bot: Bot, chat_type: str = "group") -> InlineKeyboardMarkup:
    """Builds inline keyboard with direct download button for Free Script (https://t.me/youtubewolfmod/434)"""
    download_btn = InlineKeyboardButton(
        text="🎁 Download Free Script",
        url="https://t.me/youtubewolfmod/434"
    )
    if chat_type == "private":
        buy_btn = InlineKeyboardButton(
            text="BUY VIP NOW", callback_data="show_buyvip_menu",
            icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
        )
    else:
        bot_info = await bot.get_me()
        buyvip_url = f"https://t.me/{bot_info.username}?start=buyvip"
        buy_btn = InlineKeyboardButton(
            text="BUY VIP NOW", url=buyvip_url,
            icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
        )
    return InlineKeyboardMarkup(inline_keyboard=[[download_btn], [buy_btn]])

async def build_all_scripts_keyboard(bot: Bot, chat_type: str = "group") -> InlineKeyboardMarkup:
    """Builds inline keyboard with both VIP & Free Script download buttons"""
    vip_btn = InlineKeyboardButton(
        text="Download VIP Script",
        url=config.VIP_SCRIPT_URL,
        icon_custom_emoji_id=config.VIP_SCRIPT_BUTTON_ICON_ID,
    )
    free_btn = InlineKeyboardButton(
        text="🎁 Download Free Script",
        url="https://t.me/youtubewolfmod/434"
    )
    if chat_type == "private":
        buy_btn = InlineKeyboardButton(
            text="BUY VIP NOW", callback_data="show_buyvip_menu",
            icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
        )
    else:
        bot_info = await bot.get_me()
        buyvip_url = f"https://t.me/{bot_info.username}?start=buyvip"
        buy_btn = InlineKeyboardButton(
            text="BUY VIP NOW", url=buyvip_url,
            icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
        )
    return InlineKeyboardMarkup(inline_keyboard=[[vip_btn, free_btn], [buy_btn]])

async def build_welcome_keyboard(bot: Bot) -> InlineKeyboardMarkup:
    """One button per VIP feature category (Bot API 9.4+ icon_custom_emoji_id
    puts the animated "choose" pointer on each), plus the main BUY VIP NOW
    button - all deep-link to a private chat with the bot, since unlocking
    any category means buying VIP. Brings back what used to be plain text
    only, from back when buttons couldn't show a custom emoji at all."""
    bot_info = await bot.get_me()
    buyvip_url = f"https://t.me/{bot_info.username}?start=buyvip"
    rows = []
    row = []
    for _icon, name in VIP_FEATURE_CATEGORIES:
        row.append(InlineKeyboardButton(text=name, url=buyvip_url, icon_custom_emoji_id=config.CHOOSE_ID))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text="BUY VIP NOW", url=buyvip_url,
        icon_custom_emoji_id=config.BUYVIP_BUTTON_ICON_ID,
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def handle_welcome_for_user(bot: Bot, chat_id: int, chat_title: str, user):
    """Sends welcome message if not already sent recently"""
    if not user or getattr(user, "is_bot", False):
        return
    if not should_welcome(chat_id, user.id):
        return
    try:
        welcome_text = build_welcome_text(chat_title or "THE GROUP", user.id, user.full_name)
        keyboard = await build_welcome_keyboard(bot)
        await safe_send_message(bot, chat_id, welcome_text, parse_mode="HTML", reply_markup=keyboard)
        logger.info("Sent welcome message to user %s in chat %s", user.id, chat_id)
    except Exception as e:
        logger.error("Failed to send welcome message to user %s: %s", user.id, e)

def generate_captcha_problem() -> tuple[int, int, int, list[int]]:
    """Generates (num1, num2, correct_ans, options) where options has 4 unique values shuffled"""
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    correct_ans = num1 + num2

    wrong_answers = set()
    offsets = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]
    random.shuffle(offsets)
    for off in offsets:
        cand = correct_ans + off
        if cand > 0 and cand != correct_ans:
            wrong_answers.add(cand)
        if len(wrong_answers) == 3:
            break

    cand = correct_ans + 1
    while len(wrong_answers) < 3:
        if cand != correct_ans and cand > 0:
            wrong_answers.add(cand)
        cand += 1

    options = list(wrong_answers) + [correct_ans]
    random.shuffle(options)
    return num1, num2, correct_ans, options

def build_captcha_keyboard(user_id: int, correct_ans: int, options: list[int]) -> InlineKeyboardMarkup:
    """Builds inline keyboard with 4 buttons for user verification"""
    buttons = [
        InlineKeyboardButton(
            text=str(opt),
            callback_data=f"vcap:{user_id}:{opt}:{correct_ans}"
        )
        for opt in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=[
        [buttons[0], buttons[1]],
        [buttons[2], buttons[3]]
    ])

def build_captcha_text(chat_title: str, user_id: int, user_name: str, num1: int, num2: int) -> str:
    """Builds English math captcha challenge message"""
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
    group_name = html.escape(chat_title or "OUR GROUP")
    text = (
        f"{emoji_mgr.shield} <b>MEMBER VERIFICATION</b> {emoji_mgr.shield}\n\n"
        f"👋 Welcome {user_mention} to <b>{group_name}</b>!\n"
        f"To verify that you are human and unlock sending messages, please select the correct answer below:\n\n"
        f"👉 <b>{num1} + {num2} = ?</b>\n\n"
        f"<i>(Tap 1 of the 4 buttons below to verify)</i>"
    )
    return emoji_mgr.format_msg(text)

async def start_captcha_verification(bot: Bot, chat_id: int, chat_title: str, user):
    """Restricts a newly joined member and sends a math addition captcha with 4 buttons"""
    if not user or getattr(user, "is_bot", False):
        return
    if not should_start_captcha(chat_id, user.id):
        return

    # Admins/owners bypass captcha
    try:
        if await is_admin_or_owner(chat_id, user, bot):
            await handle_welcome_for_user(bot, chat_id, chat_title, user)
            return
    except Exception:
        pass

    # 1. Restrict user from sending messages until verified
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False
    )
    try:
        await bot.restrict_chat_member(chat_id, user.id, permissions=permissions)
        logger.info("Restricted new member %s in chat %s pending captcha", user.id, chat_id)
    except Exception as e:
        logger.warning("Could not restrict new user %s in chat %s: %s", user.id, chat_id, e)

    # 2. Generate addition math problem (4 buttons)
    num1, num2, correct_ans, options = generate_captcha_problem()

    # 3. Build text and keyboard
    captcha_text = build_captcha_text(chat_title or "THE GROUP", user.id, user.full_name, num1, num2)
    keyboard = build_captcha_keyboard(user.id, correct_ans, options)

    # 4. Send captcha prompt
    try:
        sent_msg = await safe_send_message(bot, chat_id, captcha_text, parse_mode="HTML", reply_markup=keyboard)
        if sent_msg:
            _pending_captchas[(chat_id, user.id)] = {
                "num1": num1,
                "num2": num2,
                "correct_ans": correct_ans,
                "msg_id": sent_msg.message_id,
                "created_at": time.time(),
            }
            # Auto-delete unresolved captcha message after 5 minutes
            schedule_auto_delete(sent_msg, 300)
            logger.info("Sent captcha challenge to user %s in chat %s (%d + %d = %d)", user.id, chat_id, num1, num2, correct_ans)
    except Exception as e:
        logger.error("Failed to send captcha message to user %s in chat %s: %s", user.id, chat_id, e)

@router.callback_query(F.data.startswith("vcap:"))
async def on_captcha_callback(callback: CallbackQuery, bot: Bot):
    """Handles button clicks on the 4 captcha verification buttons"""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer()
        return

    try:
        target_user_id = int(parts[1])
        selected_ans = int(parts[2])
        correct_ans = int(parts[3])
    except ValueError:
        await callback.answer()
        return

    # 1. Verify if the clicking user is the user being challenged
    if callback.from_user.id != target_user_id:
        await callback.answer("⚠️ This verification is not for you!", show_alert=True)
        return

    chat_id = callback.message.chat.id

    # 2. If wrong answer, alert the user and let them retry
    if selected_ans != correct_ans:
        await callback.answer("❌ Incorrect answer! Please try again.", show_alert=True)
        return

    # 3. Correct answer! Unrestrict member
    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        await bot.restrict_chat_member(chat_id, target_user_id, permissions=permissions)
        logger.info("Unrestricted verified member %s in chat %s", target_user_id, chat_id)
    except Exception as e:
        logger.warning("Failed to unrestrict verified member %s in chat %s: %s", target_user_id, chat_id, e)

    # 4. Remove from pending list
    _pending_captchas.pop((chat_id, target_user_id), None)

    # 5. Answer callback with success alert
    await callback.answer("✅ Verified successfully! You can now send messages.", show_alert=False)

    # 6. Delete the temporary captcha prompt to keep chat clean
    try:
        await callback.message.delete()
    except Exception:
        pass

    # 7. Send the full VIP welcome message
    chat_title = callback.message.chat.title or "THE GROUP"
    await handle_welcome_for_user(bot, chat_id, chat_title, callback.from_user)

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def on_user_or_bot_join(event: ChatMemberUpdated, bot: Bot):
    """
    Catches when a new member or bot joins or is added to the group.
    """
    chat_id = event.chat.id
    new_user = event.new_chat_member.user
    inviter = event.from_user

    # Only process groups and supergroups
    if event.chat.type not in ["group", "supergroup"]:
        return

    # 1. Check if the joined member is a BOT
    if new_user.is_bot:
        bot_info = await bot.get_me()
        if new_user.id == bot_info.id:
            logger.info("Bot added to group %s (%s)", event.chat.title, chat_id)
            return

        settings = await db.get_chat_settings(chat_id)
        if settings.get("anti_bot", 1):
            is_admin = await is_admin_or_owner(chat_id, inviter, bot)

            if not is_admin:
                try:
                    # Ban/Kick the unauthorized bot immediately
                    await bot.ban_chat_member(chat_id, new_user.id)
                    await db.increment_stat(chat_id, "bot_blocked")

                    # Build English VIP notification message
                    inviter_name = html.escape(inviter.full_name) if inviter else "Unknown"
                    inviter_mention = f"<a href='tg://user?id={inviter.id}'>{inviter_name}</a>" if inviter else "Unknown"
                    bot_name = html.escape(new_user.full_name)
                    bot_username = f"@{new_user.username}" if new_user.username else f"ID: {new_user.id}"

                    alert_text = (
                        f"{emoji_mgr.shield} <b>GROUP DEFENSE - UNAUTHORIZED BOT BLOCKED</b> {emoji_mgr.vip}\n\n"
                        f"{emoji_mgr.bot} <b>Bot Detected:</b> {bot_name} ({bot_username})\n"
                        f"{emoji_mgr.warn} <b>Added By:</b> {inviter_mention}\n"
                        f"{emoji_mgr.ban} <b>Action:</b> <i>Unauthorized bot has been automatically expelled from the group!</i>\n\n"
                        f"{emoji_mgr.admin} <i>Only Group Administrators are permitted to add bots.</i>"
                    )
                    final_text = emoji_mgr.format_msg(alert_text)
                    msg = await safe_send_message(bot, chat_id, final_text, parse_mode="HTML")
                    if settings.get("auto_delete_logs", 1):
                        schedule_auto_delete(msg, config.AUTO_DELETE_LOGS_SEC)

                except Exception as e:
                    logger.error("Failed to kick unauthorized bot %s: %s", new_user.id, e)
        return

    # 2. Regular human member joined -> Save user & Start Captcha
    if new_user:
        try:
            await db.save_user(new_user.id, new_user.username or "", new_user.full_name or "")
        except Exception:
            pass
    if inviter:
        try:
            await db.save_user(inviter.id, inviter.username or "", inviter.full_name or "")
        except Exception:
            pass
    await start_captcha_verification(bot, chat_id, event.chat.title or "THE GROUP", new_user)

@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot):
    """
    Fallback handler for new chat members service message
    """
    chat_id = message.chat.id
    if message.chat.type not in ["group", "supergroup"]:
        return

    settings = await db.get_chat_settings(chat_id)
    bot_info = await bot.get_me()
    inviter = message.from_user
    is_admin = await is_admin_or_owner(chat_id, inviter, bot, sender_chat=message.sender_chat)

    for member in message.new_chat_members:
        if member and not member.is_bot:
            try:
                await db.save_user(member.id, member.username or "", member.full_name or "")
            except Exception:
                pass
        if member.is_bot:
            if member.id != bot_info.id and settings.get("anti_bot", 1) and not is_admin:
                try:
                    await bot.ban_chat_member(chat_id, member.id)
                    await db.increment_stat(chat_id, "bot_blocked")
                    
                    try:
                        await message.delete()
                    except Exception:
                        pass

                    inviter_name = html.escape(inviter.full_name) if inviter else "Unknown"
                    inviter_id = inviter.id if inviter else 0
                    inviter_mention = f"<a href='tg://user?id={inviter_id}'>{inviter_name}</a>" if inviter else "Unknown"

                    alert_text = (
                        f"{emoji_mgr.shield} <b>GROUP DEFENSE - BOT BLOCKED</b> {emoji_mgr.vip}\n\n"
                        f"{emoji_mgr.bot} <b>Bot:</b> {html.escape(member.full_name)}\n"
                        f"{emoji_mgr.warn} <b>Added By:</b> {inviter_mention}\n"
                        f"{emoji_mgr.ban} <b>Action:</b> <i>Bot has been kicked from the group!</i>"
                    )
                    final_text = emoji_mgr.format_msg(alert_text)
                    sent = await safe_answer(message, final_text, parse_mode="HTML")
                    if settings.get("auto_delete_logs", 1):
                        schedule_auto_delete(sent, config.AUTO_DELETE_LOGS_SEC)
                except Exception as e:
                    logger.error("Error auto-kicking bot: %s", e)
        else:
            # Human member joined -> Start Captcha
            await start_captcha_verification(bot, chat_id, message.chat.title or "THE GROUP", member)
