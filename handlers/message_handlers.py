import asyncio
import html
import time
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatPermissions
from database.db import db
from utils.emoji_helper import emoji_mgr, safe_answer, safe_send_message, schedule_auto_delete, get_payment_info_text, get_script_tool_info_text
from utils.auth import is_user_allowed_private, is_admin_or_owner
from utils.logger import logger
from filters.spam_filter import spam_filter
from filters.link_filter import link_filter
from filters.profanity_filter import profanity_filter
from filters.payment_filter import payment_detector
from filters.script_filter import script_detector
import config

router = Router(name="message_handlers")

async def apply_punishment(
    bot: Bot,
    chat_id: int,
    user_id: int,
    user_name: str,
    action: str,
    duration_sec: int,
    reason: str
) -> str:
    """Executes ban, mute, or kick and returns an English formatted message"""
    action_lower = action.lower()
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

    if action_lower == "ban":
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            return f"{emoji_mgr.ban} <b>PERMANENTLY BANNED:</b> {user_mention} has been permanently banned from the group for exceeding warning limits!"
        except Exception as e:
            logger.error("Failed to ban user %s: %s", user_id, e)
            return f"{emoji_mgr.error} Failed to ban member (check bot permissions): {e}"

    elif action_lower == "mute":
        try:
            until_date = datetime.now() + timedelta(seconds=duration_sec)
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )
            mins = duration_sec // 60
            dur_str = f"{mins} minutes" if mins < 60 else f"{mins // 60} hours"
            return f"{emoji_mgr.clock} {emoji_mgr.mute} <b>MUTED (TIME LIMIT):</b> {user_mention} is muted for <b>{dur_str}</b> due to rule violations!"
        except Exception as e:
            logger.error("Failed to mute user %s: %s", user_id, e)
            return f"{emoji_mgr.error} Failed to mute member: {e}"

    elif action_lower == "kick":
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            return f"{emoji_mgr.ban} <b>KICKED:</b> {user_mention} has been removed from the group for exceeding warning limits!"
        except Exception as e:
            logger.error("Failed to kick user %s: %s", user_id, e)
            return f"{emoji_mgr.error} Failed to kick member: {e}"

    return ""

@router.message(F.chat.type == "private")
async def handle_private_messages(message: Message):
    """
    Direct message handler: Communicates in Vietnamese with @wolfmodyt.
    Completely ignores unauthorized users.
    """
    user = message.from_user
    if not is_user_allowed_private(user):
        user_info = f"ID: {user.id}, Username: @{user.username}" if user else "Unknown"
        logger.info("Private message silently ignored from unauthorized user (%s)", user_info)
        return

    logger.info("Private message received from authorized user @%s (%s)", user.username, user.id)

    # Check if @wolfmodyt is testing or requesting payment info
    if payment_detector.is_payment_query(message.text or ""):
        text_pay = get_payment_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_pay), parse_mode="HTML", disable_web_page_preview=True)
        return

    # Check if @wolfmodyt is testing or requesting script/tool info
    if script_detector.is_script_query(message.text or ""):
        text_script = get_script_tool_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_script), parse_mode="HTML", disable_web_page_preview=True)
        return

    # Tiếng Việt trong tin nhắn riêng với @wolfmodyt
    text = (
        f"{emoji_mgr.vip} <b>XIN CHÀO SẾP @wolfmodyt!</b>\n\n"
        f"Tôi là bot bảo vệ nhóm & chống spam của bạn. Mọi chức năng đang hoạt động bình thường.\n"
        f"• Thêm bot vào nhóm và cấp quyền Quản trị viên để kích hoạt phòng thủ.\n"
        f"• Trong nhóm chat, bot sẽ tự động giao tiếp bằng <b>tiếng Anh</b> và xoá tin nhắn vi phạm.\n"
        f"• Gõ <code>/pay</code> để xem thông tin thanh toán (Payment Methods).\n"
        f"• Gõ <code>/script</code> để xem thông tin Tool & Script Dragon City.\n"
        f"• Gõ <code>/help</code> để xem các lệnh quản lý nhóm."
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(F.chat.type.in_(["group", "supergroup"]))
async def inspect_message(message: Message, bot: Bot):
    """
    Main moderation pipeline for group messages (in English)
    """
    # 1. 100% Exempt Anonymous Admins, Group Senders & Channel Senders
    if message.sender_chat is not None:
        return
    if message.from_user and (message.from_user.id in [1087968824, 777000] or getattr(message.from_user, "username", "") == "GroupAnonymousBot"):
        return

    user = message.from_user
    if not user or user.is_bot:
        return

    chat_id = message.chat.id
    user_id = user.id
    text = message.text or message.caption or ""

    # Check Payment Query (Bilingual English/Vietnamese keyword detection)
    if text and payment_detector.is_payment_query(text):
        text_pay = get_payment_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_pay), parse_mode="HTML", disable_web_page_preview=True)
        return

    # Check Script & Tool & VIP Key Query (Bilingual keyword detection)
    if text and script_detector.is_script_query(text):
        text_script = get_script_tool_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_script), parse_mode="HTML", disable_web_page_preview=True)
        return

    if await is_admin_or_owner(chat_id, user, bot, sender_chat=message.sender_chat):
        return

    # Load group settings
    settings = await db.get_chat_settings(chat_id)
    violation_type = None
    violation_desc = ""

    # -------------------------------------------------------------
    # 2. Check Anti-Badwords / Toxicity
    # -------------------------------------------------------------
    if settings.get("anti_badwords", 1) and text:
        is_profane, matched_word = await profanity_filter.check_profanity(text, chat_id)
        if is_profane:
            violation_type = "badwords"
            violation_desc = f"Profanity / Inappropriate language [<code>{html.escape(matched_word)}</code>]"
            await db.increment_stat(chat_id, "badwords")

    # -------------------------------------------------------------
    # 3. Check Anti-Link (if no badwords found)
    # -------------------------------------------------------------
    if not violation_type and settings.get("anti_link", 1):
        has_link, link_desc = await link_filter.check_links(message, chat_id)
        if has_link:
            violation_type = "link"
            violation_desc = f"Unauthorized link [{html.escape(link_desc)}]"
            await db.increment_stat(chat_id, "link")

    # -------------------------------------------------------------
    # 4. Check Anti-Spam / Flood (if no other violations)
    # -------------------------------------------------------------
    if not violation_type and settings.get("anti_spam", 1):
        is_spam, spam_desc = spam_filter.check_spam(chat_id, user_id, text)
        if is_spam:
            violation_type = "spam"
            violation_desc = f"{emoji_mgr.clock} Message Flood / Excessive Spam"
            await db.increment_stat(chat_id, "spam")

    # -------------------------------------------------------------
    # Handle Violation in Group (English alerts + VIP icons + 30s auto delete)
    # -------------------------------------------------------------
    if violation_type:
        # Delete offending message immediately
        try:
            await message.delete()
        except Exception:
            pass

        max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS) # Default = 2
        warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION) # Default = 'ban'
        mute_dur = settings.get("mute_duration", config.DEFAULT_MUTE_DURATION)

        # Add warning count
        current_warns = await db.add_warn(chat_id, user_id, violation_desc)
        user_name = user.full_name
        user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

        # Check if max warns reached (Quá 2 lần sẽ bị BAN khỏi group chat)
        if current_warns >= max_warns:
            punish_msg = await apply_punishment(
                bot=bot,
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                action=warn_action,
                duration_sec=mute_dur,
                reason=violation_desc
            )
            # Reset warns after punishment
            await db.reset_warns(chat_id, user_id)

            alert_text = (
                f"{emoji_mgr.shield} <b>GROUP SECURITY SYSTEM</b> {emoji_mgr.vip}\n\n"
                f"{emoji_mgr.warn} <b>Member:</b> {user_mention}\n"
                f"{emoji_mgr.ban} <b>Reason:</b> {violation_desc}\n"
                f"{emoji_mgr.error} <b>Warnings:</b> <code>{current_warns}/{max_warns}</code> (MAX REACHED)\n\n"
                f"{punish_msg}"
            )
        else:
            alert_text = (
                f"{emoji_mgr.shield} <b>SECURITY WARNING ({current_warns}/{max_warns})</b> {emoji_mgr.vip}\n\n"
                f"{emoji_mgr.warn} <b>Member:</b> {user_mention}\n"
                f"{emoji_mgr.error} <b>Violation:</b> {violation_desc}\n"
                f"{emoji_mgr.bell} <b>Action:</b> Offending message has been deleted.\n"
                f"{emoji_mgr.star} <b>Warning Count:</b> <code>{current_warns}/{max_warns}</code>\n\n"
                f"{emoji_mgr.diamond} <i>Maximum 2 warnings allowed. Exceeding 2 warnings will result in a permanent BAN!</i>"
            )

        # Append signature
        final_text = emoji_mgr.format_msg(alert_text)

        try:
            sent_msg = await safe_send_message(bot, chat_id, final_text, parse_mode="HTML")
            # Tự động xoá thông báo sau 30 giây (giữ thông báo hiện đủ 30 giây)
            if settings.get("auto_delete_logs", 1):
                schedule_auto_delete(sent_msg, config.AUTO_DELETE_LOGS_SEC)
        except Exception as e:
            logger.error("Failed to send warning alert in chat %s: %s", chat_id, e)
