import asyncio
import html
import time
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatPermissions
from database.db import db
from utils.emoji_helper import emoji_mgr
from utils.logger import logger
from filters.spam_filter import spam_filter
from filters.link_filter import link_filter
from filters.profanity_filter import profanity_filter
from handlers.member_handlers import is_user_admin
import config

router = Router(name="message_handlers")

def is_user_allowed_private(user) -> bool:
    """Checks if the user is @wolfmodyt or an Owner"""
    if not user:
        return False
    if user.id in config.OWNER_IDS:
        return True
    if user.username and user.username.lower() in config.ALLOWED_PRIVATE_USERNAMES:
        return True
    return False

async def apply_punishment(
    bot: Bot,
    chat_id: int,
    user_id: int,
    user_name: str,
    action: str,
    duration_sec: int,
    reason: str
) -> str:
    """Executes ban, mute, or kick and returns a formatted message"""
    action_lower = action.lower()
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

    if action_lower == "ban":
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            return f"{emoji_mgr.ban} Đã <b>CẤM VĨNH VIỄN (BAN)</b> {user_mention} khỏi nhóm do vượt quá số lần cảnh cáo cho phép!"
        except Exception as e:
            logger.error("Failed to ban user %s: %s", user_id, e)
            return f"{emoji_mgr.error} Không thể cấm thành viên: {e}"

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
            dur_str = f"{mins} phút" if mins < 60 else f"{mins // 60} giờ"
            return f"{emoji_mgr.clock} {emoji_mgr.mute} Đã <b>CẤM CHAT (TIME LIMIT)</b> {user_mention} trong <b>{dur_str}</b> do vi phạm quy định!"
        except Exception as e:
            logger.error("Failed to mute user %s: %s", user_id, e)
            return f"{emoji_mgr.error} Không thể cấm chat: {e}"

    elif action_lower == "kick":
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            return f"{emoji_mgr.ban} Đã <b>KICK</b> {user_mention} khỏi nhóm do vượt quá số lần cảnh cáo!"
        except Exception as e:
            logger.error("Failed to kick user %s: %s", user_id, e)
            return f"{emoji_mgr.error} Không thể kick thành viên: {e}"

    return ""

@router.message(F.chat.type == "private")
async def handle_private_messages(message: Message):
    """
    Direct message handler: Only responds to @wolfmodyt.
    Completely ignores everyone else (no response).
    """
    user = message.from_user
    if not is_user_allowed_private(user):
        # Silently ignore other users
        return

    # User is @wolfmodyt or Owner -> respond politely
    text = (
        f"{emoji_mgr.vip} <b>XIN CHÀO SẾP @wolfmodyt!</b>\n\n"
        f"Tôi là bot bảo vệ nhóm & chống spam của bạn. Mọi chức năng đang hoạt động bình thường.\n"
        f"• Thêm bot vào nhóm và cấp quyền Quản trị viên để kích hoạt phòng thủ.\n"
        f"• Gõ /help để xem các lệnh quản lý nhóm."
    )
    await message.answer(emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(F.chat.type.in_(["group", "supergroup"]))
async def inspect_message(message: Message, bot: Bot):
    """
    Main moderation pipeline for group messages
    """
    user = message.from_user
    if not user or user.is_bot:
        return

    chat_id = message.chat.id
    user_id = user.id
    text = message.text or message.caption or ""

    # 1. Exempt Admins & Group Owners
    if await is_user_admin(chat_id, user_id, bot):
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
            violation_desc = f"Ngôn từ lăng mạ / xúc phạm [<code>{html.escape(matched_word)}</code>]"
            await db.increment_stat(chat_id, "badwords")

    # -------------------------------------------------------------
    # 3. Check Anti-Link (if no badwords found)
    # -------------------------------------------------------------
    if not violation_type and settings.get("anti_link", 1):
        has_link, link_desc = await link_filter.check_links(message, chat_id)
        if has_link:
            violation_type = "link"
            violation_desc = f"Gửi liên kết trái phép [{html.escape(link_desc)}]"
            await db.increment_stat(chat_id, "link")

    # -------------------------------------------------------------
    # 4. Check Anti-Spam / Flood (if no other violations)
    # -------------------------------------------------------------
    if not violation_type and settings.get("anti_spam", 1):
        is_spam, spam_desc = spam_filter.check_spam(chat_id, user_id, text)
        if is_spam:
            violation_type = "spam"
            violation_desc = f"{emoji_mgr.clock} {spam_desc}"
            await db.increment_stat(chat_id, "spam")

    # -------------------------------------------------------------
    # Handle Violation
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

        # Add warning count (1/2, 2/2 -> max -> BAN)
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
                f"{emoji_mgr.shield} <b>HỆ THỐNG AN NINH GROUP</b> {emoji_mgr.vip}\n\n"
                f"{emoji_mgr.warn} <b>Thành viên:</b> {user_mention}\n"
                f"{emoji_mgr.ban} <b>Lý do:</b> {violation_desc}\n"
                f"{emoji_mgr.error} <b>Cảnh cáo:</b> <code>{current_warns}/{max_warns}</code> (ĐÃ ĐẠT TỐI ĐA)\n\n"
                f"{punish_msg}"
            )
        else:
            alert_text = (
                f"{emoji_mgr.shield} <b>CẢNH BÁO VI PHẠM NỘI QUY ({current_warns}/{max_warns})</b> {emoji_mgr.vip}\n\n"
                f"{emoji_mgr.warn} <b>Thành viên:</b> {user_mention}\n"
                f"{emoji_mgr.error} <b>Hành vi:</b> {violation_desc}\n"
                f"{emoji_mgr.bell} <b>Xử lý:</b> Tin nhắn đã bị xoá tự động.\n"
                f"{emoji_mgr.star} <b>Số lần cảnh cáo:</b> <code>{current_warns}/{max_warns}</code>\n\n"
                f"{emoji_mgr.diamond} <i>Cảnh cáo tối đa 2 lần, nếu tiếp tục vi phạm sẽ bị BAN vĩnh viễn khỏi nhóm!</i>"
            )

        # Append signature
        final_text = emoji_mgr.format_msg(alert_text)

        try:
            sent_msg = await bot.send_message(chat_id, final_text, parse_mode="HTML")
            # Tự động xoá sau 30 giây
            if settings.get("auto_delete_logs", 1):
                await asyncio.sleep(config.AUTO_DELETE_LOGS_SEC)
                try:
                    await sent_msg.delete()
                except Exception:
                    pass
        except Exception as e:
            logger.error("Failed to send warning alert in chat %s: %s", chat_id, e)
