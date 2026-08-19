import html
import re
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from database.db import db
from utils.emoji_helper import emoji_mgr, safe_answer, safe_send_message
from utils.logger import logger
from handlers.member_handlers import is_user_admin
from handlers.message_handlers import is_user_allowed_private
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

# -------------------------------------------------------------
# START & HELP COMMANDS
# -------------------------------------------------------------
@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    # If private chat, only respond to @wolfmodyt
    if message.chat.type == "private" and not is_user_allowed_private(message.from_user):
        return

    bot_info = await bot.get_me()
    text = (
        f"{emoji_mgr.shield} <b>XIN CHÀO! TÔI LÀ {bot_info.full_name}</b> {emoji_mgr.vip}\n\n"
        f"Bot hỗ trợ bảo vệ nhóm toàn diện, tự động hoá kiểm duyệt:\n"
        f"• {emoji_mgr.spam} <b>Chống Spam & Flood tin nhắn</b>\n"
        f"• {emoji_mgr.link} <b>Chặn gửi Link & Invite Telegram trái phép</b>\n"
        f"• {emoji_mgr.bot} <b>Chống người lạ thêm Bot khác vào Group</b>\n"
        f"• {emoji_mgr.error} <b>Chống ngôn từ lăng mạ, chửi bậy, xúc phạm</b>\n"
        f"• {emoji_mgr.ban} <b>Cảnh cáo tối đa 2 lần - Quá 2 lần tự động BAN</b>\n"
        f"• {emoji_mgr.clock} <b>Tự động xoá cảnh báo sau 30 giây</b>\n"
        f"• {emoji_mgr.diamond} <b>Hỗ trợ Icon VIP Telegram Premium Custom Emoji</b>\n\n"
        f"👉 <b>Cách sử dụng:</b> Thêm bot vào nhóm và cấp quyền <b>Quản trị viên (Admin)</b> với các quyền xoá tin nhắn và cấm thành viên.\n\n"
        f"Gõ /help để xem danh sách toàn bộ câu lệnh quản trị!"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    # If private chat, only respond to @wolfmodyt
    if message.chat.type == "private" and not is_user_allowed_private(message.from_user):
        return

    text = (
        f"{emoji_mgr.shield} <b>DANH SÁCH LỆNH QUẢN TRỊ VIÊN</b> {emoji_mgr.vip}\n\n"
        f"⚙️ <b>CÀI ĐẶT & BẢO VỆ:</b>\n"
        f"• <code>/settings</code> - Mở bảng điều khiển cài đặt bảo vệ nhóm\n"
        f"• <code>/stats</code> - Xem thống kê số lần bot đã chặn vi phạm\n\n"
        f"⚠️ <b>CẢNH CÁO & XỬ PHẠT (Tối đa 2 lần vi phạm -> BAN):</b>\n"
        f"• <code>/warn [lý do]</code> (Reply tin nhắn) - Cảnh cáo thành viên\n"
        f"• <code>/unwarn</code> (Reply tin nhắn) - Giảm 1 lần cảnh cáo\n"
        f"• <code>/warns</code> (Reply tin nhắn) - Xem số lần bị cảnh cáo\n"
        f"• <code>/mute [thời gian] [lý do]</code> - Cấm chat (vd: <code>/mute 30m</code>, <code>/mute 2h</code>, <code>/mute 1d</code>)\n"
        f"• <code>/unmute</code> (Reply tin nhắn) - Mở cấm chat cho thành viên\n"
        f"• <code>/kick [lý do]</code> (Reply tin nhắn) - Trục xuất khỏi nhóm\n"
        f"• <code>/ban [lý do]</code> (Reply tin nhắn) - Cấm vĩnh viễn khỏi nhóm\n"
        f"• <code>/unban [user_id]</code> - Gỡ cấm cho người dùng\n\n"
        f"📝 <b>TỪ CẤM & LIÊN KẾT CHO PHÉP:</b>\n"
        f"• <code>/addword [từ]</code> - Thêm từ cấm riêng cho nhóm\n"
        f"• <code>/delword [từ]</code> - Xoá từ cấm khỏi nhóm\n"
        f"• <code>/listwords</code> - Xem danh sách từ cấm nhóm\n"
        f"• <code>/addlink [tên miền]</code> - Cho phép gửi link từ web này (vd: <code>/addlink youtube.com</code>)\n"
        f"• <code>/dellink [tên miền]</code> - Xoá tên miền khỏi whitelist\n"
        f"• <code>/listlinks</code> - Xem danh sách tên miền được phép\n\n"
        f"👑 <b>TELEGRAM PREMIUM VIP CUSTOM EMOJI:</b>\n"
        f"• <code>/get_emoji</code> (Gửi kèm hoặc reply emoji VIP) - Lấy Custom Emoji ID\n"
        f"• <code>/set_emoji [key] [emoji_id]</code> - Cài đặt Custom Emoji cho bot\n"
        f"• <code>/list_emojis</code> - Xem danh sách key emoji & ID hiện hành"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# SETTINGS PANEL
# -------------------------------------------------------------
@router.message(Command("settings"))
async def cmd_settings(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        if not is_user_allowed_private(message.from_user):
            return
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng sử dụng lệnh này bên trong nhóm mà bạn muốn cấu hình!"))
        return

    if not await is_user_admin(chat_id, user_id, bot):
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Bạn phải là Quản trị viên của nhóm để sử dụng lệnh này!"))
        return

    settings = await db.get_chat_settings(chat_id)

    spam_status = "BẬT ✅" if settings.get("anti_spam", 1) else "TẮT ❌"
    link_status = "BẬT ✅" if settings.get("anti_link", 1) else "TẮT ❌"
    bot_status = "BẬT ✅" if settings.get("anti_bot", 1) else "TẮT ❌"
    badwords_status = "BẬT ✅" if settings.get("anti_badwords", 1) else "TẮT ❌"
    auto_del_status = "BẬT (30s) ✅" if settings.get("auto_delete_logs", 1) else "TẮT ❌"
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION).upper()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🔥 Anti-Spam: {spam_status}", callback_data="toggle_anti_spam"),
            InlineKeyboardButton(text=f"🔗 Anti-Link: {link_status}", callback_data="toggle_anti_link")
        ],
        [
            InlineKeyboardButton(text=f"🤖 Anti-Bot: {bot_status}", callback_data="toggle_anti_bot"),
            InlineKeyboardButton(text=f"🤬 Anti-Chửi bậy: {badwords_status}", callback_data="toggle_anti_badwords")
        ],
        [
            InlineKeyboardButton(text=f"⚠️ Giới hạn Cảnh cáo: [{max_warns}]", callback_data="cycle_max_warns"),
            InlineKeyboardButton(text=f"⚡ Hình phạt: [{warn_action}]", callback_data="cycle_warn_action")
        ],
        [
            InlineKeyboardButton(text=f"🗑️ Tự xoá tin 30s: {auto_del_status}", callback_data="toggle_auto_del")
        ],
        [
            InlineKeyboardButton(text="❌ Đóng bảng cài đặt", callback_data="close_settings")
        ]
    ])

    text = (
        f"{emoji_mgr.settings} <b>BẢNG CÀI ĐẶT BẢO VỆ NHÓM</b> {emoji_mgr.vip}\n\n"
        f"Nhấn vào các nút bên dưới để Bật/Tắt tính năng hoặc thay đổi giới hạn phạt của Bot:"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), reply_markup=keyboard, parse_mode="HTML")

# -------------------------------------------------------------
# WARN / UNWARN / WARNS
# -------------------------------------------------------------
@router.message(Command("warn"))
async def cmd_warn(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng reply tin nhắn của người cần cảnh cáo!"))
        return

    target = message.reply_to_message.from_user
    if target.id == (await bot.get_me()).id:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Không thể cảnh cáo bot!"))
        return

    if await is_user_admin(chat_id, target.id, bot):
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Không thể cảnh cáo Quản trị viên khác!"))
        return

    reason = command.args or "Vi phạm nội quy nhóm"
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION)
    mute_dur = settings.get("mute_duration", config.DEFAULT_MUTE_DURATION)

    new_warns = await db.add_warn(chat_id, target.id, reason)
    target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"
    admin_mention = f"<a href='tg://user?id={user_id}'>{html.escape(message.from_user.full_name)}</a>"

    if new_warns >= max_warns:
        from handlers.message_handlers import apply_punishment
        punish_msg = await apply_punishment(bot, chat_id, target.id, target.full_name, warn_action, mute_dur, reason)
        await db.reset_warns(chat_id, target.id)
        text = (
            f"{emoji_mgr.shield} <b>CẢNH CÁO ĐẠT GIỚI HẠN</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.warn} <b>Thành viên:</b> {target_mention}\n"
            f"{emoji_mgr.error} <b>Lý do:</b> {html.escape(reason)}\n"
            f"{emoji_mgr.star} <b>Cảnh cáo:</b> <code>{new_warns}/{max_warns}</code>\n"
            f"{punish_msg}"
        )
    else:
        text = (
            f"{emoji_mgr.warn} <b>CẢNH CÁO THÀNH VIÊN ({new_warns}/{max_warns})</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.warn} <b>Thành viên:</b> {target_mention}\n"
            f"{emoji_mgr.shield} <b>Quản trị viên:</b> {admin_mention}\n"
            f"{emoji_mgr.error} <b>Lý do:</b> {html.escape(reason)}\n"
            f"{emoji_mgr.star} <b>Số lần cảnh cáo:</b> <code>{new_warns}/{max_warns}</code>\n"
            f"{emoji_mgr.diamond} <i>Tối đa 2 lần cảnh cáo, quá 2 lần sẽ bị BAN!</i>"
        )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng reply tin nhắn của người cần xoá cảnh cáo!"))
        return

    target = message.reply_to_message.from_user
    new_warns = await db.remove_warn(chat_id, target.id)
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"

    text = (
        f"{emoji_mgr.success} Đã giảm 1 lần cảnh cáo cho {target_mention}!\n"
        f"{emoji_mgr.star} Cảnh cáo hiện tại: <code>{new_warns}/{max_warns}</code>"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("warns"))
async def cmd_warns(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type in ["private"]:
        if not is_user_allowed_private(message.from_user):
            return

    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    warn_count = await db.get_warns(chat_id, target.id)
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"

    text = (
        f"{emoji_mgr.star} <b>THÔNG TIN CẢNH CÁO</b>\n"
        f"• Thành viên: {target_mention}\n"
        f"• Số lần cảnh cáo: <code>{warn_count}/{max_warns}</code>"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# MUTE & UNMUTE
# -------------------------------------------------------------
@router.message(Command("mute"))
async def cmd_mute(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng reply tin nhắn của người cần cấm chat kèm thời gian (vd: <code>/mute 30m Spam</code>)!"))
        return

    target = message.reply_to_message.from_user
    if await is_user_admin(chat_id, target.id, bot):
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Không thể cấm chat Quản trị viên!"))
        return

    args = (command.args or "").split(maxsplit=1)
    duration_str = args[0] if len(args) > 0 else "1h"
    reason = args[1] if len(args) > 1 else "Vi phạm quy định nhóm"
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
            f"{emoji_mgr.clock} {emoji_mgr.mute} <b>ĐÃ CẤM CHAT (TIME LIMIT)</b> {emoji_mgr.vip}\n\n"
            f"• Thành viên: {target_mention}\n"
            f"• Thời hạn: <b>{duration_str}</b>\n"
            f"• Lý do: {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Lỗi khi cấm chat: {e}"))

@router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng reply tin nhắn của người cần mở cấm chat!"))
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
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.success} Đã gỡ cấm chat cho {target_mention}!"), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Lỗi khi gỡ cấm chat: {e}"))

# -------------------------------------------------------------
# KICK & BAN & UNBAN
# -------------------------------------------------------------
@router.message(Command("kick"))
async def cmd_kick(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng reply tin nhắn của người cần kick!"))
        return

    target = message.reply_to_message.from_user
    if await is_user_admin(chat_id, target.id, bot):
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Không thể kick Quản trị viên!"))
        return

    reason = command.args or "Bị kick bởi Quản trị viên"
    try:
        await bot.ban_chat_member(chat_id, target.id)
        await bot.unban_chat_member(chat_id, target.id)
        target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"
        text = (
            f"{emoji_mgr.ban} <b>ĐÃ KICK THÀNH VIÊN</b>\n"
            f"• Thành viên: {target_mention}\n"
            f"• Lý do: {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Lỗi khi kick: {e}"))

@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng reply tin nhắn của người cần cấm vĩnh viễn!"))
        return

    target = message.reply_to_message.from_user
    if await is_user_admin(chat_id, target.id, bot):
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Không thể ban Quản trị viên!"))
        return

    reason = command.args or "Bị cấm bởi Quản trị viên"
    try:
        await bot.ban_chat_member(chat_id, target.id)
        target_mention = f"<a href='tg://user?id={target.id}'>{html.escape(target.full_name)}</a>"
        text = (
            f"{emoji_mgr.ban} <b>ĐÃ CẤM VĨNH VIỄN (BAN)</b> {emoji_mgr.vip}\n"
            f"• Thành viên: {target_mention}\n"
            f"• Lý do: {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Lỗi khi cấm thành viên: {e}"))

@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    if not command.args or not command.args.strip().isdigit():
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Vui lòng nhập User ID cần gỡ cấm (vd: <code>/unban 123456789</code>)!"))
        return

    target_id = int(command.args.strip())
    try:
        await bot.unban_chat_member(chat_id, target_id)
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.success} Đã gỡ cấm thành công cho ID <code>{target_id}</code>!"), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Lỗi khi gỡ cấm: {e}"))

# -------------------------------------------------------------
# BANNED WORDS MANAGEMENT
# -------------------------------------------------------------
@router.message(Command("addword"))
async def cmd_addword(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(chat_id, user_id, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Cú pháp: <code>/addword [từ cấm]</code>"))
        return
    word = command.args.strip().lower()
    success = await db.add_banned_word(chat_id, word, user_id)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.success} Đã thêm từ <b>{html.escape(word)}</b> vào danh sách cấm của nhóm!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Từ này đã có trong danh sách cấm!"))

@router.message(Command("delword"))
async def cmd_delword(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(chat_id, user_id, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Cú pháp: <code>/delword [từ cần xoá]</code>"))
        return
    word = command.args.strip().lower()
    success = await db.remove_banned_word(chat_id, word)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.success} Đã xoá từ <b>{html.escape(word)}</b> khỏi danh sách cấm!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Không tìm thấy từ này trong danh sách cấm!"))

@router.message(Command("listwords"))
async def cmd_listwords(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(chat_id, user_id, bot):
        return
    words = await db.get_banned_words(chat_id)
    if not words:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.shield} Nhóm đang dùng danh sách từ cấm mặc định."))
        return
    words_str = ", ".join([f"<code>{html.escape(w)}</code>" for w in words[:50]])
    text = f"{emoji_mgr.shield} <b>DANH SÁCH TỪ CẤM NHÓM ({len(words)} từ):</b>\n{words_str}"
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# WHITELIST LINK MANAGEMENT
# -------------------------------------------------------------
@router.message(Command("addlink"))
async def cmd_addlink(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(chat_id, user_id, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Cú pháp: <code>/addlink [tên miền]</code> (vd: <code>/addlink youtube.com</code>)"))
        return
    domain = command.args.strip().lower()
    success = await db.add_whitelist_link(chat_id, domain)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.success} Đã thêm <b>{html.escape(domain)}</b> vào whitelist!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Tên miền này đã có trong whitelist!"))

@router.message(Command("dellink"))
async def cmd_dellink(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(chat_id, user_id, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Cú pháp: <code>/dellink [tên miền]</code>"))
        return
    domain = command.args.strip().lower()
    success = await db.remove_whitelist_link(chat_id, domain)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.success} Đã xoá <b>{html.escape(domain)}</b> khỏi whitelist!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Không tìm thấy tên miền trong whitelist!"))

@router.message(Command("listlinks"))
async def cmd_listlinks(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(chat_id, user_id, bot):
        return
    links = await db.get_whitelist_links(chat_id)
    if not links:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.link} Whitelist liên kết đang trống (tất cả link bên ngoài đều bị chặn)."))
        return
    links_str = "\n".join([f"• <code>{html.escape(l)}</code>" for l in links])
    text = f"{emoji_mgr.link} <b>DANH SÁCH LIÊN KẾT ĐƯỢC PHÉP ({len(links)}):</b>\n{links_str}"
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# TELEGRAM PREMIUM CUSTOM EMOJI TOOLS
# -------------------------------------------------------------
@router.message(Command("get_emoji", "getemoji"))
async def cmd_get_emoji(message: Message):
    """
    Scans the message or replied message for Telegram Premium Custom Emoji entities
    and returns their IDs for easy copying!
    """
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
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in config.OWNER_IDS and not await is_user_admin(message.chat.id, user_id, bot):
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Bạn không có quyền thực hiện lệnh này!"))
        return

    if not command.args:
        text = (
            f"{emoji_mgr.settings} <b>CÀI ĐẶT VIP CUSTOM EMOJI</b>\n\n"
            f"Cú pháp: <code>/set_emoji [key] [emoji_id] [kí tự fallback]</code>\n"
            f"Ví dụ: <code>/set_emoji vip 5368324170671202286 👑</code>\n\n"
            f"<b>Các key hợp lệ:</b>\n"
            f"<code>vip</code>, <code>shield</code>, <code>warn</code>, <code>ban</code>, <code>mute</code>, <code>link</code>, <code>bot</code>, <code>spam</code>, <code>clock</code>, <code>tele_logo</code>, <code>success</code>, <code>error</code>, <code>diamond</code>, <code>settings</code>"
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
        f"{emoji_mgr.success} Đã cập nhật Custom Emoji cho key <b>{html.escape(key)}</b> thành công!\n"
        f"• Xem trước: <tg-emoji emoji-id='{emoji_id}'>{fallback}</tg-emoji> (ID: <code>{emoji_id}</code>)"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("list_emojis", "listemojis"))
async def cmd_list_emojis(message: Message):
    await emoji_mgr.load_emojis()
    lines = [f"{emoji_mgr.vip} <b>DANH SÁCH KEY CUSTOM EMOJI ĐANG DÙNG:</b>\n"]

    all_keys = ["tele_logo", "clock", "vip", "shield", "warn", "ban", "mute", "link", "bot", "spam", "success", "error", "settings", "diamond"]
    for k in all_keys:
        icon_rendered = emoji_mgr.get(k)
        conf_id = config.DEFAULT_EMOJIS.get(k, {}).get("id", "Mặc định")
        db_val = emoji_mgr._db_emojis.get(k, {}).get("id")
        current_id = db_val if db_val else (conf_id if conf_id else "Chưa gán ID")
        lines.append(f"• <b>{k.upper()}:</b> {icon_rendered} | ID: <code>{current_id}</code>")

    lines.append(f"\n💡 <i>Dùng <code>/get_emoji</code> để lấy ID từ tài khoản Telegram Premium.</i>")
    await safe_answer(message, emoji_mgr.format_msg("\n".join(lines)), parse_mode="HTML")

# -------------------------------------------------------------
# STATS COMMAND
# -------------------------------------------------------------
@router.message(Command("stats"))
async def cmd_stats(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if message.chat.type in ["private"]:
        return
    if not await is_user_admin(chat_id, user_id, bot):
        return

    stats = await db.get_stats(chat_id)
    spam_count = stats.get("spam", 0)
    link_count = stats.get("link", 0)
    badwords_count = stats.get("badwords", 0)
    bot_count = stats.get("bot_blocked", 0)
    total = spam_count + link_count + badwords_count + bot_count

    text = (
        f"{emoji_mgr.shield} <b>THỐNG KÊ AN NINH NHÓM</b> {emoji_mgr.vip}\n\n"
        f"• {emoji_mgr.spam} <b>Spam & Flood đã chặn:</b> <code>{spam_count}</code>\n"
        f"• {emoji_mgr.link} <b>Link trái phép đã xoá:</b> <code>{link_count}</code>\n"
        f"• {emoji_mgr.error} <b>Ngôn từ lăng mạ đã xử lý:</b> <code>{badwords_count}</code>\n"
        f"• {emoji_mgr.bot} <b>Bot lạ đã trục xuất:</b> <code>{bot_count}</code>\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"🏆 <b>Tổng số vi phạm đã ngăn chặn:</b> <code>{total}</code>"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
