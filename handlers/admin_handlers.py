import html
import re
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from database.db import db
from utils.emoji_helper import (
    emoji_mgr,
    safe_answer,
    safe_send_message,
    schedule_auto_delete,
    get_payment_info_text,
    get_script_tool_info_text
)
from utils.auth import is_user_allowed_private, is_admin_or_owner
from utils.logger import logger
import config

router = Router(name="admin_handlers")

def parse_time_duration(time_str: str) -> int:
    """Parses duration string like 10m, 1h, 2d, 1w into seconds"""
    if not time_str:
        return 3600 # Default 1 hour
    unit = time_str[-1].lower()
    value_str = time_str[:-1]
    if not value_str.isdigit():
        return 3600
    val = int(value_str)
    if unit == 'm':
        return val * 60
    elif unit == 'h':
        return val * 3600
    elif unit == 'd':
        return val * 86400
    elif unit == 'w':
        return val * 604800
    elif time_str.isdigit():
        return int(time_str) * 60
    return 3600

async def require_admin(message: Message, bot: Bot) -> bool:
    """
    Ensures that only @wolfmodyt, Owner IDs, and Group Administrators
    can execute administrative/moderation commands.
    If a regular member attempts, delete command and send a 30s auto-delete warning.
    """
    chat_id = message.chat.id
    if not await is_admin_or_owner(chat_id, message.from_user, bot, sender_chat=message.sender_chat):
        try:
            await message.delete()
        except Exception:
            pass
        if message.chat.type != "private":
            warn_txt = (
                f"{emoji_mgr.error} <b>ACCESS DENIED</b> {emoji_mgr.vip}\n\n"
                f"{emoji_mgr.warn} Regular members are <b>not permitted</b> to use Administrator commands!\n"
                f"{emoji_mgr.admin} Only Group Admins & {emoji_mgr.vip} :@wolfmodyt can perform this action."
            )
            err_msg = await safe_answer(message, emoji_mgr.format_msg(warn_txt), parse_mode="HTML")
            schedule_auto_delete(err_msg, 30)
        return False
    return True

# -------------------------------------------------------------
# START & HELP COMMANDS (Bilingual: VN in private, EN in group)
# -------------------------------------------------------------
@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return

    bot_info = await bot.get_me()

    if is_private:
        # Tiếng Việt trong tin nhắn riêng
        text = (
            f"{emoji_mgr.shield} <b>XIN CHÀO! TÔI LÀ {bot_info.full_name}</b> {emoji_mgr.vip}\n\n"
            f"Bot hỗ trợ bảo vệ nhóm toàn diện, tự động hoá kiểm duyệt:\n"
            f"{emoji_mgr.star} {emoji_mgr.spam} <b>Chống Spam & Flood tin nhắn</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.link} <b>Chặn gửi Link & Invite Telegram trái phép</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.shield} <b>Chống người lạ thêm Bot khác vào Group</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.error} <b>Chống ngôn từ lăng mạ, chửi bậy, xúc phạm</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.ban} <b>Cảnh cáo tối đa 2 lần - Quá 2 lần tự động BAN</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.clock} <b>Tự động xoá cảnh báo sau 30 giây</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.diamond} <b>Hỗ trợ Icon VIP Telegram Premium Custom Emoji</b>\n\n"
            f"{emoji_mgr.diamond} <b>Cách sử dụng:</b> Thêm bot vào nhóm và cấp quyền <b>Quản trị viên (Admin)</b> với các quyền xoá tin nhắn và cấm thành viên.\n\n"
            f"Gõ <code>/help</code> để xem danh sách toàn bộ câu lệnh quản trị!"
        )
    else:
        # English in Group
        text = (
            f"{emoji_mgr.shield} <b>HELLO! I AM {bot_info.full_name}</b> {emoji_mgr.vip}\n\n"
            f"Advanced Group Security & Anti-Spam Guard Bot:\n"
            f"{emoji_mgr.star} {emoji_mgr.spam} <b>Anti-Spam & Message Flood Protection</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.link} <b>Anti-Link & Unauthorized Telegram Invites</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.shield} <b>Anti-Bot (Unauthorized bot invites blocked)</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.error} <b>Anti-Profanity & Toxicity Filter</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.ban} <b>Max 2 Warnings - Exceeding 2 results in BAN</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.clock} <b>Auto-delete violation logs after 30 seconds</b>\n"
            f"{emoji_mgr.star} {emoji_mgr.diamond} <b>Telegram Premium VIP Custom Emoji support</b>\n\n"
            f"{emoji_mgr.diamond} <b>Admin Guide:</b> Type <code>/help</code> for available commands and <code>/settings</code> to configure group rules."
        )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return

    if is_private:
        # Tiếng Việt trong tin nhắn riêng
        text = (
            f"{emoji_mgr.shield} <b>DANH SÁCH LỆNH QUẢN TRỊ VIÊN</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.settings} <b>CÀI ĐẶT & BẢO VỆ:</b>\n"
            f"{emoji_mgr.star} <code>/settings</code> - Mở bảng điều khiển cài đặt bảo vệ nhóm\n"
            f"{emoji_mgr.star} <code>/pay</code> - Xem thông tin thanh toán (Payment Methods)\n"
            f"{emoji_mgr.star} <code>/script</code> - Xem thông tin Tool & Script Dragon City\n"
            f"{emoji_mgr.star} <code>/stats</code> - Xem thống kê số lần bot đã chặn vi phạm\n\n"
            f"{emoji_mgr.warn} <b>CẢNH CÁO & XỬ PHẠT (Tối đa 2 lần vi phạm -> BAN):</b>\n"
            f"{emoji_mgr.star} <code>/warn [lý do]</code> (Reply tin nhắn) - Cảnh cáo thành viên\n"
            f"{emoji_mgr.star} <code>/unwarn</code> (Reply tin nhắn) - Giảm 1 lần cảnh cáo\n"
            f"{emoji_mgr.star} <code>/warns</code> (Reply tin nhắn) - Xem số lần bị cảnh cáo\n"
            f"{emoji_mgr.star} <code>/mute [thời gian] [lý do]</code> - Cấm chat (vd: <code>/mute 30m</code>, <code>/mute 2h</code>, <code>/mute 1d</code>)\n"
            f"{emoji_mgr.star} <code>/unmute</code> (Reply tin nhắn) - Mở cấm chat cho thành viên\n"
            f"{emoji_mgr.star} <code>/kick [lý do]</code> (Reply tin nhắn) - Trục xuất khỏi nhóm\n"
            f"{emoji_mgr.star} <code>/ban [lý do]</code> (Reply tin nhắn) - Cấm vĩnh viễn khỏi nhóm\n"
            f"{emoji_mgr.star} <code>/unban [user_id]</code> - Gỡ cấm cho người dùng\n\n"
            f"{emoji_mgr.link} <b>TỪ CẤM & LIÊN KẾT CHO PHÉP:</b>\n"
            f"{emoji_mgr.star} <code>/addword [từ]</code> - Thêm từ cấm riêng cho nhóm\n"
            f"{emoji_mgr.star} <code>/delword [từ]</code> - Xoá từ cấm khỏi nhóm\n"
            f"{emoji_mgr.star} <code>/listwords</code> - Xem danh sách từ cấm nhóm\n"
            f"{emoji_mgr.star} <code>/addlink [tên miền]</code> - Cho phép gửi link từ web này (vd: <code>/addlink youtube.com</code>)\n"
            f"{emoji_mgr.star} <code>/dellink [tên miền]</code> - Xoá tên miền khỏi whitelist\n"
            f"{emoji_mgr.star} <code>/listlinks</code> - Xem danh sách tên miền được phép\n\n"
            f"{emoji_mgr.vip} <b>TELEGRAM PREMIUM VIP CUSTOM EMOJI:</b>\n"
            f"{emoji_mgr.star} <code>/get_emoji</code> (Gửi kèm hoặc reply emoji VIP) - Lấy Custom Emoji ID\n"
            f"{emoji_mgr.star} <code>/set_emoji [key] [emoji_id]</code> - Cài đặt Custom Emoji cho bot\n"
            f"{emoji_mgr.star} <code>/list_emojis</code> - Xem danh sách key emoji & ID hiện hành"
        )
    else:
        # English in Group
        text = (
            f"{emoji_mgr.shield} <b>ADMINISTRATOR COMMANDS LIST</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.settings} <b>SETTINGS & STATS:</b>\n"
            f"{emoji_mgr.star} <code>/settings</code> - Open interactive group security panel\n"
            f"{emoji_mgr.star} <code>/pay</code> - View Payment Methods\n"
            f"{emoji_mgr.star} <code>/script</code> - View Dragon City Tool & Script Link\n"
            f"{emoji_mgr.star} <code>/stats</code> - View security and violation statistics\n\n"
            f"{emoji_mgr.warn} <b>MODERATION (Max 2 Warnings -> BAN):</b>\n"
            f"{emoji_mgr.star} <code>/warn [reason]</code> (Reply message) - Warn member\n"
            f"{emoji_mgr.star} <code>/unwarn</code> (Reply message) - Remove 1 warning\n"
            f"{emoji_mgr.star} <code>/warns</code> (Reply message) - Check warnings count\n"
            f"{emoji_mgr.star} <code>/mute [duration] [reason]</code> - Mute user (e.g. <code>/mute 30m</code>, <code>/mute 2h</code>)\n"
            f"{emoji_mgr.star} <code>/unmute</code> (Reply message) - Unmute member\n"
            f"{emoji_mgr.star} <code>/kick [reason]</code> (Reply message) - Kick member from group\n"
            f"{emoji_mgr.star} <code>/ban [reason]</code> (Reply message) - Ban member permanently\n"
            f"{emoji_mgr.star} <code>/unban [user_id]</code> - Unban user by ID\n\n"
            f"{emoji_mgr.link} <b>CUSTOM BLACKLIST & WHITELIST:</b>\n"
            f"{emoji_mgr.star} <code>/addword [word]</code> - Add banned word\n"
            f"{emoji_mgr.star} <code>/delword [word]</code> - Remove banned word\n"
            f"{emoji_mgr.star} <code>/listwords</code> - View banned words list\n"
            f"{emoji_mgr.star} <code>/addlink [domain]</code> - Whitelist domain (e.g. <code>/addlink youtube.com</code>)\n"
            f"{emoji_mgr.star} <code>/dellink [domain]</code> - Remove domain from whitelist\n"
            f"{emoji_mgr.star} <code>/listlinks</code> - View whitelisted domains\n\n"
            f"{emoji_mgr.vip} <b>VIP CUSTOM EMOJIS:</b>\n"
            f"{emoji_mgr.star} <code>/get_emoji</code> - Extract Telegram Premium Custom Emoji IDs\n"
            f"{emoji_mgr.star} <code>/set_emoji [key] [id]</code> - Configure custom emoji icon\n"
            f"{emoji_mgr.star} <code>/list_emojis</code> - View active custom emoji IDs"
        )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# PAYMENT METHODS COMMAND (/pay, /payment, /bank, /donate, /buy)
# -------------------------------------------------------------
@router.message(Command("pay", "payment", "pricing", "price", "bank", "donate", "buy"))
async def cmd_payment(message: Message):
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return

    text = get_payment_info_text()
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML", disable_web_page_preview=True)

# -------------------------------------------------------------
# SCRIPT & TOOL & VIP KEY COMMAND (/script, /tool, /key, /free, /dragoncity, /dc)
# -------------------------------------------------------------
@router.message(Command("script", "tool", "key", "free", "vipkey", "dragoncity", "dc"))
async def cmd_script(message: Message):
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return

    text = get_script_tool_info_text()
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML", disable_web_page_preview=True)

# -------------------------------------------------------------
# GET CHAT ID / USER ID COMMAND (/id, /chatid, /info)
# -------------------------------------------------------------
@router.message(Command("id", "chatid", "info"))
async def cmd_id(message: Message, bot: Bot):
    chat = message.chat
    user = message.from_user
    sender_chat = message.sender_chat
    reply = message.reply_to_message

    lines = [f"{emoji_mgr.shield} <b>TELEGRAM ID INFORMATION</b> {emoji_mgr.vip}\n"]
    
    if chat.type in ["group", "supergroup", "channel"]:
        lines.append(f"• {emoji_mgr.star} <b>Group / Chat Title:</b> {html.escape(chat.title or 'Group')}")
        lines.append(f"• {emoji_mgr.star} <b>Group Chat ID:</b> <code>{chat.id}</code>")
        if message.message_thread_id:
            lines.append(f"• {emoji_mgr.star} <b>Topic ID:</b> <code>{message.message_thread_id}</code>")
    else:
        lines.append(f"• {emoji_mgr.star} <b>Chat Type:</b> Private Chat")

    if sender_chat:
        lines.append(f"• {emoji_mgr.admin} <b>Sender (Anonymous/Channel):</b> {html.escape(sender_chat.title or '')} (ID: <code>{sender_chat.id}</code>)")
    elif user:
        uname = f" (@{user.username})" if user.username else ""
        lines.append(f"• {emoji_mgr.admin} <b>Your User ID:</b> <code>{user.id}</code>{uname}")

    if reply:
        r_user = reply.from_user
        r_sender = reply.sender_chat
        if r_sender:
            lines.append(f"• {emoji_mgr.diamond} <b>Replied Chat/Channel:</b> {html.escape(r_sender.title or '')} (ID: <code>{r_sender.id}</code>)")
        elif r_user:
            r_uname = f" (@{r_user.username})" if r_user.username else ""
            lines.append(f"• {emoji_mgr.diamond} <b>Replied User ID:</b> <code>{r_user.id}</code> ({html.escape(r_user.full_name)}){r_uname}")

    text = "\n".join(lines)
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# SETTINGS PANEL (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("settings"))
async def cmd_settings(message: Message, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"

    if is_private:
        if not is_user_allowed_private(message.from_user):
            return
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng sử dụng lệnh này bên trong nhóm mà bạn muốn cấu hình!"))
        return

    if not await require_admin(message, bot):
        return

    settings = await db.get_chat_settings(chat_id)

    spam_status = "ON ✅" if settings.get("anti_spam", 1) else "OFF ❌"
    link_status = "ON ✅" if settings.get("anti_link", 1) else "OFF ❌"
    bot_status = "ON ✅" if settings.get("anti_bot", 1) else "OFF ❌"
    badwords_status = "ON ✅" if settings.get("anti_badwords", 1) else "OFF ❌"
    auto_del_status = "ON (30s) ✅" if settings.get("auto_delete_logs", 1) else "OFF ❌"
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION).upper()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🔥 Anti-Spam: {spam_status}", callback_data="toggle_anti_spam"),
            InlineKeyboardButton(text=f"🔗 Anti-Link: {link_status}", callback_data="toggle_anti_link")
        ],
        [
            InlineKeyboardButton(text=f"🤖 Anti-Bot: {bot_status}", callback_data="toggle_anti_bot"),
            InlineKeyboardButton(text=f"🤬 Anti-Profanity: {badwords_status}", callback_data="toggle_anti_badwords")
        ],
        [
            InlineKeyboardButton(text=f"⚠️ Max Warnings: [{max_warns}]", callback_data="cycle_max_warns"),
            InlineKeyboardButton(text=f"⚡ Punishment: [{warn_action}]", callback_data="cycle_warn_action")
        ],
        [
            InlineKeyboardButton(text=f"🗑️ Auto-delete 30s: {auto_del_status}", callback_data="toggle_auto_del")
        ],
        [
            InlineKeyboardButton(text="❌ Close Settings", callback_data="close_settings")
        ]
    ])

    text = (
        f"{emoji_mgr.settings} <b>GROUP SECURITY SETTINGS PANEL</b> {emoji_mgr.vip}\n\n"
        f"Click the buttons below to toggle security modules or change punishment rules:"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), reply_markup=keyboard, parse_mode="HTML")

# -------------------------------------------------------------
# WARN / UNWARN / WARNS (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("warn"))
async def cmd_warn(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return

    if not await require_admin(message, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Please reply to the user's message to warn them!"))
        schedule_auto_delete(err_msg, 30)
        return

    target = message.reply_to_message.from_user
    target_sender_chat = message.reply_to_message.sender_chat
    if target and target.id == (await bot.get_me()).id:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot warn the bot!"))
        schedule_auto_delete(err_msg, 30)
        return

    if await is_admin_or_owner(chat_id, target, bot, sender_chat=target_sender_chat):
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot warn another Administrator!"))
        schedule_auto_delete(err_msg, 30)
        return

    reason = command.args or "Group rules violation"
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION)
    mute_dur = settings.get("mute_duration", config.DEFAULT_MUTE_DURATION)

    target_id = target.id if target else (target_sender_chat.id if target_sender_chat else 0)
    target_name = target.full_name if target else (target_sender_chat.title if target_sender_chat else "User")
    new_warns = await db.add_warn(chat_id, target_id, reason)
    target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
    
    if message.sender_chat:
        admin_mention = f"<b>{html.escape(message.sender_chat.title)}</b> ({emoji_mgr.vip} Admin)"
    elif message.from_user:
        admin_mention = f"<a href='tg://user?id={message.from_user.id}'>{html.escape(message.from_user.full_name)}</a>"
    else:
        admin_mention = f"<b>Group Admin</b>"

    if new_warns >= max_warns:
        from handlers.message_handlers import apply_punishment
        punish_msg = await apply_punishment(bot, chat_id, target.id, target.full_name, warn_action, mute_dur, reason)
        await db.reset_warns(chat_id, target.id)
        text = (
            f"{emoji_mgr.shield} <b>MAX WARNINGS REACHED</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.warn} <b>Member:</b> {target_mention}\n"
            f"{emoji_mgr.error} <b>Reason:</b> {html.escape(reason)}\n"
            f"{emoji_mgr.star} <b>Warnings:</b> <code>{new_warns}/{max_warns}</code>\n"
            f"{punish_msg}"
        )
    else:
        text = (
            f"{emoji_mgr.warn} <b>MEMBER WARNED ({new_warns}/{max_warns})</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.warn} <b>Member:</b> {target_mention}\n"
            f"{emoji_mgr.admin} <b>Admin:</b> {admin_mention}\n"
            f"{emoji_mgr.error} <b>Reason:</b> {html.escape(reason)}\n"
            f"{emoji_mgr.star} <b>Warnings:</b> <code>{new_warns}/{max_warns}</code>\n"
            f"{emoji_mgr.diamond} <i>Max 2 warnings allowed. Exceeding 2 warnings will result in a BAN!</i>"
        )
    sent_msg = await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    if settings.get("auto_delete_logs", 1):
        schedule_auto_delete(sent_msg, config.AUTO_DELETE_LOGS_SEC)

@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Please reply to the user's message to remove a warning!"))
        schedule_auto_delete(err_msg, 30)
        return

    target = message.reply_to_message.from_user
    new_warns = await db.remove_warn(chat_id, target.id)
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"

    text = (
        f"{emoji_mgr.star} Removed 1 warning for {target_mention}!\n"
        f"{emoji_mgr.star} Current Warnings: <code>{new_warns}/{max_warns}</code>"
    )
    sent_msg = await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    if settings.get("auto_delete_logs", 1):
        schedule_auto_delete(sent_msg, config.AUTO_DELETE_LOGS_SEC)

@router.message(Command("warns"))
async def cmd_warns(message: Message, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return

    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    warn_count = await db.get_warns(chat_id, target.id)
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"

    if is_private:
        text = (
            f"{emoji_mgr.star} <b>THÔNG TIN CẢNH CÁO</b>\n"
            f"• Thành viên: {target_mention}\n"
            f"• Số lần cảnh cáo: <code>{warn_count}/{max_warns}</code>"
        )
    else:
        text = (
            f"{emoji_mgr.star} <b>WARNING STATUS</b>\n"
            f"• Member: {target_mention}\n"
            f"• Warnings: <code>{warn_count}/{max_warns}</code>"
        )
    sent_msg = await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    if not is_private and settings.get("auto_delete_logs", 1):
        schedule_auto_delete(sent_msg, config.AUTO_DELETE_LOGS_SEC)

# -------------------------------------------------------------
# MUTE & UNMUTE (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("mute"))
async def cmd_mute(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Please reply to the user message with duration (e.g. <code>/mute 30m Spam</code>)!"))
        schedule_auto_delete(err_msg, 30)
        return

    target = message.reply_to_message.from_user
    target_sender_chat = message.reply_to_message.sender_chat
    if await is_admin_or_owner(chat_id, target, bot, sender_chat=target_sender_chat):
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot mute an Administrator!"))
        schedule_auto_delete(err_msg, 30)
        return

    args = (command.args or "").split(maxsplit=1)
    duration_str = args[0] if len(args) > 0 else "1h"
    reason = args[1] if len(args) > 1 else "Group rules violation"
    duration_sec = parse_time_duration(duration_str)

    until_date = datetime.now() + timedelta(seconds=duration_sec)
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False
    )
    try:
        await bot.restrict_chat_member(chat_id, target.id, permissions=permissions, until_date=until_date)
        target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"
        text = (
            f"{emoji_mgr.clock} {emoji_mgr.mute} <b>MEMBER MUTED (TIME LIMIT)</b> {emoji_mgr.vip}\n\n"
            f"• Member: {target_mention}\n"
            f"• Duration: <b>{duration_str}</b>\n"
            f"• Reason: {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error muting user: {e}"))

@router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Please reply to the user message to unmute!"))
        schedule_auto_delete(err_msg, 30)
        return

    target = message.reply_to_message.from_user
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True
    )
    try:
        await bot.restrict_chat_member(chat_id, target.id, permissions=permissions)
        target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} Unmuted {target_mention} successfully!"), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error unmuting user: {e}"))

# -------------------------------------------------------------
# KICK & BAN & UNBAN (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("kick"))
async def cmd_kick(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Please reply to the user message to kick!"))
        schedule_auto_delete(err_msg, 30)
        return

    target = message.reply_to_message.from_user
    target_sender_chat = message.reply_to_message.sender_chat
    if await is_admin_or_owner(chat_id, target, bot, sender_chat=target_sender_chat):
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot kick an Administrator!"))
        schedule_auto_delete(err_msg, 30)
        return

    reason = command.args or "Kicked by Administrator"
    try:
        target_id = target.id if target else target_sender_chat.id
        await bot.ban_chat_member(chat_id, target_id)
        await bot.unban_chat_member(chat_id, target_id)
        target_name = target.full_name if target else target_sender_chat.title
        target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
        text = (
            f"{emoji_mgr.ban} <b>MEMBER KICKED</b>\n"
            f"• Member: {target_mention}\n"
            f"• Reason: {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error kicking user: {e}"))

@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    if not message.reply_to_message or not (message.reply_to_message.from_user or message.reply_to_message.sender_chat):
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Please reply to the user message to ban!"))
        schedule_auto_delete(err_msg, 30)
        return

    target = message.reply_to_message.from_user
    target_sender_chat = message.reply_to_message.sender_chat
    if await is_admin_or_owner(chat_id, target, bot, sender_chat=target_sender_chat):
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot ban an Administrator!"))
        schedule_auto_delete(err_msg, 30)
        return

    reason = command.args or "Banned by Administrator"
    try:
        target_id = target.id if target else target_sender_chat.id
        await bot.ban_chat_member(chat_id, target_id)
        target_name = target.full_name if target else target_sender_chat.title
        target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
        text = (
            f"{emoji_mgr.ban} <b>PERMANENTLY BANNED</b> {emoji_mgr.vip}\n\n"
            f"• Member: {target_mention}\n"
            f"• Reason: {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error banning user: {e}"))

@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    if not command.args or not command.args.strip().isdigit():
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Usage: <code>/unban [user_id]</code> (e.g. <code>/unban 123456789</code>)!"))
        schedule_auto_delete(err_msg, 30)
        return

    target_id = int(command.args.strip())
    try:
        await bot.unban_chat_member(chat_id, target_id)
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} Unbanned ID <code>{target_id}</code> successfully!"), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error unbanning: {e}"))

# -------------------------------------------------------------
# BANNED WORDS MANAGEMENT (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("addword"))
async def cmd_addword(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if not await require_admin(message, bot):
        return
    if not command.args:
        usage_msg = "Cú pháp: <code>/addword [từ cấm]</code>" if is_private else "Usage: <code>/addword [word]</code>"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} {usage_msg}"))
        return
    word = command.args.strip().lower()
    success = await db.add_banned_word(chat_id, word, message.from_user.id if message.from_user else 0)
    if success:
        ok_msg = f"Đã thêm từ <b>{html.escape(word)}</b> vào danh sách cấm!" if is_private else f"Added <b>{html.escape(word)}</b> to banned words list!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} {ok_msg}"), parse_mode="HTML")
    else:
        dup_msg = "Từ này đã có trong danh sách cấm!" if is_private else "This word is already in the blacklist!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} {dup_msg}"))

@router.message(Command("delword"))
async def cmd_delword(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if not await require_admin(message, bot):
        return
    if not command.args:
        usage_msg = "Cú pháp: <code>/delword [từ cần xoá]</code>" if is_private else "Usage: <code>/delword [word]</code>"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} {usage_msg}"))
        return
    word = command.args.strip().lower()
    success = await db.remove_banned_word(chat_id, word)
    if success:
        ok_msg = f"Đã xoá từ <b>{html.escape(word)}</b> khỏi danh sách cấm!" if is_private else f"Removed <b>{html.escape(word)}</b> from blacklist!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} {ok_msg}"), parse_mode="HTML")
    else:
        err_msg = "Không tìm thấy từ này trong danh sách cấm!" if is_private else "Word not found in blacklist!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} {err_msg}"))

@router.message(Command("listwords"))
async def cmd_listwords(message: Message, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if not await require_admin(message, bot):
        return
    words = await db.get_banned_words(chat_id)
    if not words:
        empty_msg = "Nhóm đang dùng danh sách từ cấm mặc định." if is_private else "Using default global blacklist."
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.shield} {empty_msg}"))
        return
    words_str = ", ".join([f"<code>{html.escape(w)}</code>" for w in words[:50]])
    title_msg = f"DANH SÁCH TỪ CẤM ({len(words)} từ):" if is_private else f"BANNED WORDS LIST ({len(words)} words):"
    text = f"{emoji_mgr.shield} <b>{title_msg}</b>\n{words_str}"
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# WHITELIST LINK MANAGEMENT (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("addlink"))
async def cmd_addlink(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if not await require_admin(message, bot):
        return
    if not command.args:
        usage_msg = "Cú pháp: <code>/addlink [tên miền]</code> (vd: <code>/addlink youtube.com</code>)" if is_private else "Usage: <code>/addlink [domain]</code> (e.g. <code>/addlink youtube.com</code>)"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} {usage_msg}"))
        return
    domain = command.args.strip().lower()
    success = await db.add_whitelist_link(chat_id, domain)
    if success:
        ok_msg = f"Đã thêm <b>{html.escape(domain)}</b> vào whitelist!" if is_private else f"Added <b>{html.escape(domain)}</b> to whitelist!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} {ok_msg}"), parse_mode="HTML")
    else:
        dup_msg = "Tên miền này đã có trong whitelist!" if is_private else "Domain is already in whitelist!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} {dup_msg}"))

@router.message(Command("dellink"))
async def cmd_dellink(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if not await require_admin(message, bot):
        return
    if not command.args:
        usage_msg = "Cú pháp: <code>/dellink [tên miền]</code>" if is_private else "Usage: <code>/dellink [domain]</code>"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} {usage_msg}"))
        return
    domain = command.args.strip().lower()
    success = await db.remove_whitelist_link(chat_id, domain)
    if success:
        ok_msg = f"Đã xoá <b>{html.escape(domain)}</b> khỏi whitelist!" if is_private else f"Removed <b>{html.escape(domain)}</b> from whitelist!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} {ok_msg}"), parse_mode="HTML")
    else:
        err_msg = "Không tìm thấy tên miền trong whitelist!" if is_private else "Domain not found in whitelist!"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} {err_msg}"))

@router.message(Command("listlinks"))
async def cmd_listlinks(message: Message, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if not await require_admin(message, bot):
        return
    links = await db.get_whitelist_links(chat_id)
    if not links:
        empty_msg = "Whitelist liên kết đang trống (tất cả link bên ngoài đều bị chặn)." if is_private else "Link whitelist is empty (all external links blocked)."
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.link} {empty_msg}"))
        return
    links_str = "\n".join([f"• <code>{html.escape(l)}</code>" for l in links])
    title_msg = f"DANH SÁCH LIÊN KẾT ĐƯỢC PHÉP ({len(links)}):" if is_private else f"WHITELISTED DOMAINS ({len(links)}):"
    text = f"{emoji_mgr.link} <b>{title_msg}</b>\n{links_str}"
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# TELEGRAM PREMIUM CUSTOM EMOJI TOOLS (Accessible to @wolfmodyt)
# -------------------------------------------------------------
@router.message(Command("get_emoji", "getemoji"))
async def cmd_get_emoji(message: Message, bot: Bot):
    if not await require_admin(message, bot):
        return

    target_msg = message.reply_to_message if message.reply_to_message else message
    entities = (target_msg.entities or []) + (target_msg.caption_entities or [])
    full_text = target_msg.text or target_msg.caption or ""

    found_emojis = []
    for ent in entities:
        if ent.type == "custom_emoji" and hasattr(ent, "custom_emoji_id"):
            ent_char = full_text[ent.offset : ent.offset + ent.length] if full_text else "Icon"
            found_emojis.append((ent.custom_emoji_id, ent_char))

    if not found_emojis:
        text = (
            f"{emoji_mgr.warn} <b>KHÔNG TÌM THẤY CUSTOM EMOJI!</b>\n\n"
            f"💡 <b>Hướng dẫn sử dụng:</b>\n"
            f"1. Hãy gửi một tin nhắn chứa các icon/sticker động Telegram Premium của bạn.\n"
            f"2. Reply tin nhắn đó và gõ lệnh: <code>/get_emoji</code>\n"
            f"Hoặc gõ <code>/get_emoji</code> kèm emoji VIP trong cùng 1 tin nhắn.\n\n"
            f"Bot sẽ trích xuất mã ID để bạn gán vào bot!"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
        return

    output_lines = [f"{emoji_mgr.vip} <b>TÌM THẤY {len(found_emojis)} TELEGRAM PREMIUM CUSTOM EMOJI:</b>\n"]
    for idx, (emoji_id, char) in enumerate(found_emojis, 1):
        output_lines.append(
            f"<b>#{idx}</b> <tg-emoji emoji-id='{emoji_id}'>{char}</tg-emoji>\n"
            f"• <b>Emoji ID:</b> <code>{emoji_id}</code>\n"
            f"• <b>Mẫu gắn:</b> <code>/set_emoji vip {emoji_id}</code>\n"
        )
    output_lines.append(f"\n{emoji_mgr.diamond} <i>Bạn có thể dùng lệnh /set_emoji [key] [id] để cập nhật ngay!</i>")
    await safe_answer(message, emoji_mgr.format_msg("\n".join(output_lines)), parse_mode="HTML")

@router.message(Command("set_emoji", "setemoji"))
async def cmd_set_emoji(message: Message, command: CommandObject, bot: Bot):
    if not await require_admin(message, bot):
        return

    if not command.args:
        text = (
            f"{emoji_mgr.settings} <b>CÀI ĐẶT VIP CUSTOM EMOJI</b>\n\n"
            f"Cú pháp: <code>/set_emoji [key] [emoji_id] [kí tự fallback]</code>\n"
            f"Ví dụ: <code>/set_emoji vip 5217822164362739968 👑</code>\n\n"
            f"<b>Các key hợp lệ:</b>\n"
            f"<code>vip</code>, <code>shield</code>, <code>warn</code>, <code>ban</code>, <code>mute</code>, <code>link</code>, <code>spam</code>, <code>clock</code>, <code>tele_logo</code>, <code>error</code>, <code>diamond</code>, <code>star</code>, <code>bell</code>, <code>settings</code>"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
        return

    parts = command.args.split()
    if len(parts) < 2:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Vui lòng cung cấp cả [key] và [emoji_id]!"))
        return

    key = parts[0].lower().strip()
    emoji_id = parts[1].strip()
    fallback = parts[2].strip() if len(parts) > 2 else "✨"

    if not emoji_id.isdigit():
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Emoji ID phải là chuỗi số nguyên hợp lệ!"))
        return

    await db.set_custom_emoji(key, emoji_id, fallback)
    await emoji_mgr.load_emojis()

    text = (
        f"{emoji_mgr.star} Đã cập nhật Custom Emoji cho key <b>{html.escape(key)}</b> thành công!\n"
        f"• Xem trước: <tg-emoji emoji-id='{emoji_id}'>{fallback}</tg-emoji> (ID: <code>{emoji_id}</code>)"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("list_emojis", "listemojis"))
async def cmd_list_emojis(message: Message, bot: Bot):
    if not await require_admin(message, bot):
        return

    await emoji_mgr.load_emojis()
    lines = [f"{emoji_mgr.vip} <b>DANH SÁCH KEY CUSTOM EMOJI ĐANG DÙNG:</b>\n"]

    all_keys = ["tele_logo", "clock", "vip", "shield", "warn", "ban", "mute", "link", "spam", "error", "settings", "diamond", "star", "bell"]
    for k in all_keys:
        icon_rendered = emoji_mgr.get(k)
        conf_id = config.DEFAULT_EMOJIS.get(k, {}).get("id", "")
        db_val = emoji_mgr._db_emojis.get(k, {}).get("id")
        current_id = db_val if db_val else (conf_id if conf_id else "Chưa gán ID")
        lines.append(f"• <b>{k.upper()}:</b> {icon_rendered} | ID: <code>{current_id}</code>")

    lines.append(f"\n💡 <i>Dùng <code>/get_emoji</code> để lấy ID từ tài khoản Telegram Premium.</i>")
    await safe_answer(message, emoji_mgr.format_msg("\n".join(lines)), parse_mode="HTML")

# -------------------------------------------------------------
# STATS COMMAND (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("stats"))
async def cmd_stats(message: Message, bot: Bot):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return
    if not is_private and not await require_admin(message, bot):
        return

    stats = await db.get_stats(chat_id)
    spam_count = stats.get("spam", 0)
    link_count = stats.get("link", 0)
    badwords_count = stats.get("badwords", 0)
    bot_count = stats.get("bot_blocked", 0)
    total = spam_count + link_count + badwords_count + bot_count

    if is_private:
        text = (
            f"{emoji_mgr.shield} <b>THỐNG KÊ AN NINH NHÓM</b> {emoji_mgr.vip}\n\n"
            f"• {emoji_mgr.spam} <b>Spam & Flood đã chặn:</b> <code>{spam_count}</code>\n"
            f"• {emoji_mgr.link} <b>Link trái phép đã xoá:</b> <code>{link_count}</code>\n"
            f"• {emoji_mgr.error} <b>Ngôn từ lăng mạ đã xử lý:</b> <code>{badwords_count}</code>\n"
            f"• {emoji_mgr.shield} <b>Bot lạ đã trục xuất:</b> <code>{bot_count}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji_mgr.star} <b>Tổng số vi phạm đã ngăn chặn:</b> <code>{total}</code>"
        )
    else:
        text = (
            f"{emoji_mgr.shield} <b>GROUP SECURITY STATISTICS</b> {emoji_mgr.vip}\n\n"
            f"• {emoji_mgr.spam} <b>Spam & Flood blocked:</b> <code>{spam_count}</code>\n"
            f"• {emoji_mgr.link} <b>Unauthorized Links removed:</b> <code>{link_count}</code>\n"
            f"• {emoji_mgr.error} <b>Profanity filtered:</b> <code>{badwords_count}</code>\n"
            f"• {emoji_mgr.shield} <b>Unauthorized Bots blocked:</b> <code>{bot_count}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji_mgr.star} <b>Total violations prevented:</b> <code>{total}</code>"
        )
    sent_msg = await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    if not is_private:
        settings = await db.get_chat_settings(chat_id)
        if settings.get("auto_delete_logs", 1):
            schedule_auto_delete(sent_msg, config.AUTO_DELETE_LOGS_SEC)
