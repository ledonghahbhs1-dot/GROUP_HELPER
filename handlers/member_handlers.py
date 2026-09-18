import asyncio
import html
import time
from aiogram import Router, F, Bot
from aiogram.types import ChatMemberUpdated, Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
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
        f"{emoji_mgr.vip} <b>WELCOME TO {group_name.upper()}!</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Welcome member:</b> {user_mention} (<code>{user_id}</code>)\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.shield} <b>ADMIN & SUPPORT CONTACT:</b>\n"
        f"• {emoji_mgr.vip} <b>Owner / Master Admin:</b> @wolfmodyt {emoji_mgr.vip}\n"
        f"• {emoji_mgr.star} <b>Payment Methods (VIP Key):</b> Type <code>pay</code> in chat or DM {emoji_mgr.vip} :@wolfmodyt\n"
        f"• {emoji_mgr.star} <b>Dragon City Tool & Script:</b> Type <code>tool</code> or <code>script</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>DRAGON CITY VIP FEATURES</b> 🔥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "".join(f"{icon} {name}\n" for icon, name in VIP_FEATURE_CATEGORIES)
        + f"\n{emoji_mgr.star} <i>Tap a category below to unlock it with VIP!</i>\n\n"
        f"{emoji_mgr.warn} <b>GROUP SECURITY & RULES:</b>\n"
        f"• {emoji_mgr.error} No spamming or excessive flood messages\n"
        f"• {emoji_mgr.link} No unauthorized links / Telegram invite links\n"
        f"• {emoji_mgr.bot} No forwarded messages from bots / inline bots\n"
        f"• {emoji_mgr.warn} <i>Violators will receive warnings (5 warnings = PERMANENT BAN).</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.diamond} <i>Wishing you a wonderful experience!</i>"
    )
    return emoji_mgr.format_msg(text)

async def handle_welcome_for_user(bot: Bot, chat_id: int, chat_title: str, user):
    """Sends welcome message if not already sent recently"""
    if not user or user.is_bot:
        return
    if not should_welcome(chat_id, user.id):
        return
    try:
        welcome_text = build_welcome_text(chat_title or "THE GROUP", user.id, user.full_name)
        bot_info = await bot.get_me()
        buyvip_url = f"https://t.me/{bot_info.username}?start=buyvip"

        # Every VIP feature category is itself a "Buy VIP Now" entry point (2 per row),
        # plus one prominent full-width button at the bottom. The rules/warnings section
        # above intentionally gets no button.
        category_buttons = [
            InlineKeyboardButton(text=f"{icon} {name}", url=buyvip_url)
            for icon, name in VIP_FEATURE_CATEGORIES
        ]
        category_rows = [category_buttons[i:i + 2] for i in range(0, len(category_buttons), 2)]
        keyboard = InlineKeyboardMarkup(inline_keyboard=category_rows + [
            [InlineKeyboardButton(text="💎 BUY VIP NOW", url=buyvip_url)]
        ])
        await safe_send_message(bot, chat_id, welcome_text, parse_mode="HTML", reply_markup=keyboard)
        logger.info("Sent welcome message to user %s in chat %s", user.id, chat_id)
    except Exception as e:
        logger.error("Failed to send welcome message to user %s: %s", user.id, e)

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

    # 2. Regular human member joined -> Send Welcome & Admin Info
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
    await handle_welcome_for_user(bot, chat_id, event.chat.title or "THE GROUP", new_user)

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
            # Human member joined
            await handle_welcome_for_user(bot, chat_id, message.chat.title or "THE GROUP", member)
