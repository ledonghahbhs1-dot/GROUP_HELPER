import html
import re
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject, Filter
from database.db import db
from utils.emoji_helper import (
    emoji_mgr,
    safe_answer,
    safe_send_message,
    schedule_auto_delete,
    get_payment_info_text,
    get_script_tool_info_text,
    get_pricing_info_text,
    get_features_info_text
)
from utils.auth import is_user_allowed_private, is_admin_or_owner
from utils.logger import logger
import config

router = Router(name="admin_handlers")

class PlainAdminCommandFilter(Filter):
    async def __call__(self, message: Message) -> bool | dict:
        text = (message.text or "").strip()
        if not text or text.startswith(('/', '!')):
            return False
        parsed = parse_admin_cmd(text, bool(message.reply_to_message))
        if parsed:
            return {"parsed_admin_cmd": parsed}
        return False

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

async def resolve_target(
    message: Message,
    bot: Optional[Bot] = None,
    command: Optional[CommandObject] = None,
    raw_args: str = ""
) -> tuple[Optional[int], str, str]:
    """
    Resolves target_id, target_name, and remaining arguments from:
    1. First argument if numeric Telegram User ID (e.g. /ban 123456789 spam or warn 123456789 spam)
    2. First argument if Telegram @username (e.g. /unban @masteroogwayv1 or unwarn @masteroogwayv1)
    3. Text mentions in message.entities
    4. Reply message (reply_to_message.from_user or reply_to_message.sender_chat)
    Returns: (target_id, target_name, remaining_args)
    """
    args_str = (command.args if command and command.args else raw_args).strip()
    if args_str:
        parts = args_str.split(maxsplit=1)
        first_tok = parts[0].strip()
        rem = parts[1].strip() if len(parts) > 1 else ""

        # 1. Numeric ID
        if first_tok.lstrip("-").isdigit():
            t_id = int(first_tok)
            cached = await db.get_user_by_id(t_id)
            name = cached["full_name"] if cached and cached.get("full_name") else f"User {t_id}"
            return t_id, name, rem

        # 2. Explicit @username (e.g. @masteroogwayv1)
        if first_tok.startswith("@"):
            clean_uname = first_tok.lstrip("@").strip().lower()
            if clean_uname:
                # 2.1 Check text_mention in entities
                for entity in (getattr(message, "entities", None) or []):
                    if entity.type == "text_mention" and entity.user:
                        u = entity.user
                        u_uname = (u.username or "").lower()
                        if u_uname == clean_uname or not u_uname:
                            await db.save_user(u.id, u.username or "", u.full_name or "")
                            return u.id, u.full_name or f"@{clean_uname}", rem

                # 2.2 Check Database user cache & banned users
                cached = await db.get_user_by_username(clean_uname)
                if cached and cached.get("user_id"):
                    name = cached.get("full_name") or f"@{cached.get('username', clean_uname)}"
                    return cached["user_id"], name, rem

                chat_obj = getattr(message, "chat", None)
                c_id = getattr(chat_obj, "id", None) if chat_obj else None
                banned_cached = await db.get_banned_user_by_username(clean_uname, chat_id=c_id)
                if banned_cached and banned_cached.get("user_id"):
                    name = banned_cached.get("full_name") or f"@{banned_cached.get('username', clean_uname)}"
                    return banned_cached["user_id"], name, rem

                # 2.3 Check group administrators
                if bot and chat_obj and getattr(chat_obj, "type", "") in ["group", "supergroup"]:
                    try:
                        admins = await bot.get_chat_administrators(chat_obj.id)
                        for adm in admins:
                            if adm.user and (adm.user.username or "").lower() == clean_uname:
                                await db.save_user(adm.user.id, adm.user.username or "", adm.user.full_name or "")
                                return adm.user.id, adm.user.full_name or f"@{clean_uname}", rem
                    except Exception:
                        pass

                # 2.4 Try Telegram API bot.get_chat(@username)
                if bot:
                    try:
                        chat_obj_tg = await bot.get_chat(f"@{clean_uname}")
                        if chat_obj_tg and chat_obj_tg.id:
                            name = chat_obj_tg.full_name or f"@{clean_uname}"
                            await db.save_user(chat_obj_tg.id, clean_uname, name)
                            return chat_obj_tg.id, name, rem
                    except Exception:
                        pass

                # If explicit @username not found anywhere
                return None, f"@{clean_uname}", rem

    # 3. Reply to message
    if message.reply_to_message:
        if message.reply_to_message.from_user:
            u = message.reply_to_message.from_user
            await db.save_user(u.id, u.username or "", u.full_name or "")
            u_name = getattr(u, "full_name", None) or getattr(u, "first_name", None) or getattr(u, "username", None) or f"User {u.id}"
            return u.id, u_name, args_str
        elif message.reply_to_message.sender_chat:
            sc = message.reply_to_message.sender_chat
            sc_title = getattr(sc, "title", "Channel")
            return sc.id, sc_title, args_str

    # 4. Fallback: if not a reply and first_tok is a known username in database
    if args_str:
        parts = args_str.split(maxsplit=1)
        first_tok = parts[0].strip()
        rem = parts[1].strip() if len(parts) > 1 else ""
        clean_uname = first_tok.lstrip("@").strip().lower()
        if clean_uname:
            cached = await db.get_user_by_username(clean_uname)
            if cached and cached.get("user_id"):
                name = cached.get("full_name") or f"@{cached.get('username', clean_uname)}"
                return cached["user_id"], name, rem

    return None, "", args_str

def parse_admin_cmd(text: str, has_reply: bool) -> Optional[tuple[str, str]]:
    """
    Parses moderation commands like 'warn 123456789 spam' or 'unban @masteroogwayv1' or 'warn' (reply).
    Returns (command_name, args_string) or None if normal chat text.
    """
    text = (text or "").strip()
    m = re.match(r'^(?:/|!|)(warn|ban|unwarn|unban|resetwarns|clearwarns|mute|unmute|kick|warns|banlist|banned)\b(?:\s+(.*))?$', text, re.IGNORECASE)
    if not m:
        return None
    cmd = m.group(1).lower()
    args = (m.group(2) or "").strip()
    if cmd in ["banlist", "banned"]:
        return cmd, args
    is_slash = text.startswith(('/', '!'))
    if not is_slash:
        if not has_reply:
            parts = args.split(maxsplit=1)
            if not parts:
                return None
            first_tok = parts[0].strip()
            # Allow numeric ID (123456789) OR @username (@masteroogwayv1) OR alphanumeric username
            if not (first_tok.lstrip('-').isdigit() or first_tok.startswith('@') or (len(first_tok) >= 3 and re.match(r'^[a-zA-Z0-9_]+$', first_tok))):
                return None
    return cmd, args

# -------------------------------------------------------------
# START & HELP COMMANDS (Bilingual: VN in private, EN in group)
# -------------------------------------------------------------
@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot, command: CommandObject):
    is_private = message.chat.type == "private"

    # "Buy VIP Key" deep link (from the group welcome message button) - open to ANY user,
    # bypassing the owner-only private chat restriction below.
    if is_private and command.args == "buyvip":
        from handlers.vip_handlers import send_vip_plan_menu
        await send_vip_plan_menu(bot, message.chat.id)
        return

    if is_private and not is_user_allowed_private(message.from_user):
        return

    bot_info = await bot.get_me()

    text = (
        f"{emoji_mgr.shield} <b>HELLO! I AM {bot_info.full_name}</b> {emoji_mgr.vip}\n\n"
        f"Advanced Group Security & Anti-Spam Guard Bot:\n"
        f"{emoji_mgr.star} {emoji_mgr.spam} <b>Anti-Spam & Message Flood Protection</b>\n"
        f"{emoji_mgr.star} {emoji_mgr.link} <b>Anti-Link & Unauthorized Telegram Invites</b>\n"
        f"{emoji_mgr.star} {emoji_mgr.shield} <b>Anti-Bot (Unauthorized bot invites blocked)</b>\n"
        f"{emoji_mgr.star} {emoji_mgr.error} <b>Anti-Profanity & Toxicity Filter</b>\n"
        f"{emoji_mgr.star} {emoji_mgr.ban} <b>Max 5 Warnings - Exceeding 5 results in BAN</b>\n"
        f"{emoji_mgr.star} {emoji_mgr.clock} <b>Auto-delete violation logs after 30 seconds</b>\n"
        f"{emoji_mgr.star} {emoji_mgr.diamond} <b>Telegram Premium VIP Custom Emoji support</b>\n\n"
        f"{emoji_mgr.diamond} <b>Admin Guide:</b> Add bot as Administrator with delete and ban permissions. Type <code>/help</code> for available commands and <code>/settings</code> to configure group rules."
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return

    text = (
        f"{emoji_mgr.shield} <b>ADMINISTRATOR COMMANDS LIST</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.settings} <b>SETTINGS & STATS:</b>\n"
        f"{emoji_mgr.star} <code>/settings</code> - Open interactive group security panel\n"
        f"{emoji_mgr.star} <code>/features</code> - View VIP & Free script detailed feature list\n"
        f"{emoji_mgr.star} <code>/price</code> - View VIP Key Pricing & Packages\n"
        f"{emoji_mgr.star} <code>/pay</code> - View Payment Methods\n"
        f"{emoji_mgr.star} <code>/script</code> - View Dragon City Tool & Script Link\n"
        f"{emoji_mgr.star} <code>/stats</code> - View security and violation statistics\n\n"
        f"{emoji_mgr.warn} <b>MODERATION (Max 5 Warnings -> BAN):</b>\n"
        f"{emoji_mgr.star} <code>/warn [user_id / @username / reply] [reason]</code> - Warn member\n"
        f"{emoji_mgr.star} <code>/unwarn [user_id / @username / reply]</code> - Remove 1 warning\n"
        f"{emoji_mgr.star} <code>/warns [user_id / @username / reply]</code> - Check warnings count\n"
        f"{emoji_mgr.star} <code>/mute [user_id / @username / reply] [duration] [reason]</code> - Mute user (e.g. <code>/mute 30m</code>)\n"
        f"{emoji_mgr.star} <code>/unmute [user_id / @username / reply]</code> - Unmute member\n"
        f"{emoji_mgr.star} <code>/kick [user_id / @username / reply] [reason]</code> - Kick member from group\n"
        f"{emoji_mgr.star} <code>/ban [user_id / @username / reply] [reason]</code> - Ban member permanently\n"
        f"{emoji_mgr.star} <code>/unban [user_id / @username]</code> - Unban user\n"
        f"{emoji_mgr.star} <code>/banlist</code> - View banned list and 1-click unban buttons\n\n"
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
# FEATURES COMMAND (/features, /feature, /tinhnang, /chucnang, /menu)
# -------------------------------------------------------------
@router.message(Command("features", "feature", "tinhnang", "chucnang", "menu"))
async def cmd_features(message: Message):
    text = get_features_info_text()
    full_text = emoji_mgr.format_msg(text)
    try:
        await message.answer(full_text, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        await message.answer(emoji_mgr.strip_tg_emojis(full_text), parse_mode="HTML", disable_web_page_preview=True)

# -------------------------------------------------------------
# PRICING COMMAND (/price, /pricing, /cost, /rate, /rates, /gia)
# -------------------------------------------------------------
@router.message(Command("price", "pricing", "cost", "rate", "rates", "gia"))
async def cmd_price(message: Message):
    text = get_pricing_info_text()
    full_text = emoji_mgr.format_msg(text)
    try:
        await message.answer(full_text, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        await message.answer(emoji_mgr.strip_tg_emojis(full_text), parse_mode="HTML", disable_web_page_preview=True)

# -------------------------------------------------------------
# PAYMENT METHODS COMMAND (/pay, /payment, /bank, /donate, /buy, /stk)
# -------------------------------------------------------------
@router.message(Command("pay", "payment", "bank", "donate", "buy", "stk"))
async def cmd_payment(message: Message):
    text = get_payment_info_text()
    full_text = emoji_mgr.format_msg(text)
    try:
        await message.answer(full_text, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        await message.answer(emoji_mgr.strip_tg_emojis(full_text), parse_mode="HTML", disable_web_page_preview=True)

# -------------------------------------------------------------
# SCRIPT & TOOL & VIP KEY COMMAND (/script, /tool, /key, /free, /dragoncity, /dc)
# -------------------------------------------------------------
@router.message(Command("script", "tool", "key", "free", "vipkey", "dragoncity", "dc"))
async def cmd_script(message: Message):
    text = get_script_tool_info_text()
    full_text = emoji_mgr.format_msg(text)
    try:
        await message.answer(full_text, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        await message.answer(emoji_mgr.strip_tg_emojis(full_text), parse_mode="HTML", disable_web_page_preview=True)

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
        lines.append(f"{emoji_mgr.star} <b>Group / Chat Title:</b> {html.escape(chat.title or 'Group')}")
        lines.append(f"{emoji_mgr.star} <b>Group Chat ID:</b> <code>{chat.id}</code>")
        if message.message_thread_id:
            lines.append(f"{emoji_mgr.star} <b>Topic ID:</b> <code>{message.message_thread_id}</code>")
    else:
        lines.append(f"{emoji_mgr.star} <b>Chat Type:</b> Private Chat")

    if sender_chat:
        lines.append(f"{emoji_mgr.admin} <b>Sender (Anonymous/Channel):</b> {html.escape(sender_chat.title or '')} (ID: <code>{sender_chat.id}</code>)")
    elif user:
        uname = f" (@{user.username})" if user.username else ""
        lines.append(f"{emoji_mgr.admin} <b>Your User ID:</b> <code>{user.id}</code>{uname}")

    if reply:
        r_user = reply.from_user
        r_sender = reply.sender_chat
        if r_sender:
            lines.append(f"{emoji_mgr.diamond} <b>Replied Chat/Channel:</b> {html.escape(r_sender.title or '')} (ID: <code>{r_sender.id}</code>)")
        elif r_user:
            r_uname = f" (@{r_user.username})" if r_user.username else ""
            lines.append(f"{emoji_mgr.diamond} <b>Replied User ID:</b> <code>{r_user.id}</code> ({html.escape(r_user.full_name)}){r_uname}")

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
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Please use this command inside the group you wish to configure!"))
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
async def execute_warn(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return

    if not await require_admin(message, bot):
        return

    target_id, target_name, reason = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please reply directly to their message or enter User ID (e.g. <code>/warn 123456789</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/warn @masteroogwayv1 [reason]</code> or <code>/warn 123456789 [reason]</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    bot_me = await bot.get_me()
    if target_id == bot_me.id:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot warn the bot!"))
        schedule_auto_delete(err_msg, 30)
        return

    if message.reply_to_message and message.reply_to_message.from_user:
        if await is_admin_or_owner(chat_id, message.reply_to_message.from_user, bot, sender_chat=message.reply_to_message.sender_chat):
            err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot warn another Administrator!"))
            schedule_auto_delete(err_msg, 30)
            return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    reason = reason or "Group rules violation"
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION)
    mute_dur = settings.get("mute_duration", config.DEFAULT_MUTE_DURATION)

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
        punish_msg = await apply_punishment(bot, chat_id, target_id, target_name, warn_action, mute_dur, reason)
        await db.reset_warns(chat_id, target_id)
        text = (
            f"{emoji_mgr.shield} <b>MAX WARNINGS REACHED ({new_warns}/{max_warns})</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.warn} <b>Member:</b> {target_mention} (<code>{target_id}</code>)\n"
            f"{emoji_mgr.error} <b>Reason:</b> {html.escape(reason)}\n"
            f"{emoji_mgr.star} <b>Warnings:</b> <code>{new_warns}/{max_warns}</code>\n"
            f"{punish_msg}"
        )
    else:
        text = (
            f"{emoji_mgr.warn} <b>MEMBER WARNED ({new_warns}/{max_warns})</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.warn} <b>Member:</b> {target_mention} (<code>{target_id}</code>)\n"
            f"{emoji_mgr.admin} <b>Admin:</b> {admin_mention}\n"
            f"{emoji_mgr.error} <b>Reason:</b> {html.escape(reason)}\n"
            f"{emoji_mgr.star} <b>Warnings:</b> <code>{new_warns}/{max_warns}</code>\n"
            f"{emoji_mgr.diamond} <i>Max {max_warns} warnings allowed. Exceeding {max_warns} warnings will result in a PERMANENT BAN!</i>"
        )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("warn", prefix="/!"))
async def cmd_warn(message: Message, command: CommandObject, bot: Bot):
    await execute_warn(message, bot, command=command)

async def execute_unwarn(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    target_id, target_name, _ = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please reply directly to their message or enter User ID (e.g. <code>/unwarn 123456789</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/unwarn @masteroogwayv1</code> or <code>/unwarn 123456789</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    new_warns = await db.remove_warn(chat_id, target_id)
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"

    text = (
        f"{emoji_mgr.star} Removed 1 warning for {target_mention} (<code>{target_id}</code>)!\n"
        f"{emoji_mgr.star} Current Warnings: <code>{new_warns}/{max_warns}</code>"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("unwarn", prefix="/!"))
async def cmd_unwarn(message: Message, command: CommandObject, bot: Bot):
    await execute_unwarn(message, bot, command=command)

async def execute_warns(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    if is_private and not is_user_allowed_private(message.from_user):
        return

    target_id, target_name, _ = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if message.from_user:
            target_id = message.from_user.id
            target_name = message.from_user.full_name
        else:
            err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please reply, enter @username, or User ID (e.g. <code>/warns @masteroogwayv1</code> or <code>/warns 123456789</code>)!"))
            schedule_auto_delete(err_msg, 30)
            return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    warn_count = await db.get_warns(chat_id, target_id)
    settings = await db.get_chat_settings(chat_id)
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"

    text = (
        f"{emoji_mgr.shield} <b>WARNING STATUS</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Member:</b> {target_mention}\n"
        f"{emoji_mgr.warn} <b>Warnings:</b> <code>{warn_count}/{max_warns}</code>"
    )
    sent_msg = await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    if not is_private and settings.get("auto_delete_logs", 1):
        schedule_auto_delete(sent_msg, config.AUTO_DELETE_LOGS_SEC)

@router.message(Command("warns", prefix="/!"))
async def cmd_warns(message: Message, command: CommandObject, bot: Bot):
    await execute_warns(message, bot, command=command)

# -------------------------------------------------------------
# MUTE & UNMUTE (ADMIN ONLY)
# -------------------------------------------------------------
async def execute_mute(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    target_id, target_name, rem_args = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please reply directly to their message or enter User ID (e.g. <code>/mute 123456789 30m</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/mute @masteroogwayv1 30m [reason]</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    bot_me = await bot.get_me()
    if target_id == bot_me.id:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot mute the bot!"))
        schedule_auto_delete(err_msg, 30)
        return

    if message.reply_to_message and message.reply_to_message.from_user:
        if await is_admin_or_owner(chat_id, message.reply_to_message.from_user, bot, sender_chat=message.reply_to_message.sender_chat):
            err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot mute an Administrator!"))
            schedule_auto_delete(err_msg, 30)
            return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    args = rem_args.split(maxsplit=1)
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
        await bot.restrict_chat_member(chat_id, target_id, permissions=permissions, until_date=until_date)
        target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
        text = (
            f"{emoji_mgr.clock} {emoji_mgr.mute} <b>MEMBER MUTED (TIME LIMIT)</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.star} <b>Member:</b> {target_mention} (<code>{target_id}</code>)\n"
            f"{emoji_mgr.clock} <b>Duration:</b> <b>{duration_str}</b>\n"
            f"{emoji_mgr.error} <b>Reason:</b> {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error muting user: {e}"))

@router.message(Command("mute", prefix="/!"))
async def cmd_mute(message: Message, command: CommandObject, bot: Bot):
    await execute_mute(message, bot, command=command)

async def execute_unmute(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    target_id, target_name, _ = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please reply directly to their message or enter User ID (e.g. <code>/unmute 123456789</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/unmute @masteroogwayv1</code> hoặc <code>/unmute 123456789</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True
    )
    try:
        await bot.restrict_chat_member(chat_id, target_id, permissions=permissions)
        target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} Unmuted {target_mention} (<code>{target_id}</code>) successfully!"), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error unmuting user: {e}"))

@router.message(Command("unmute", prefix="/!"))
async def cmd_unmute(message: Message, command: CommandObject, bot: Bot):
    await execute_unmute(message, bot, command=command)

# -------------------------------------------------------------
# KICK & BAN & UNBAN (ADMIN ONLY)
# -------------------------------------------------------------
async def execute_kick(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    target_id, target_name, reason = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please reply directly to their message or enter User ID (e.g. <code>/kick 123456789</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/kick @masteroogwayv1 [reason]</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    bot_me = await bot.get_me()
    if target_id == bot_me.id:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot kick the bot!"))
        schedule_auto_delete(err_msg, 30)
        return

    if message.reply_to_message and message.reply_to_message.from_user:
        if await is_admin_or_owner(chat_id, message.reply_to_message.from_user, bot, sender_chat=message.reply_to_message.sender_chat):
            err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot kick an Administrator!"))
            schedule_auto_delete(err_msg, 30)
            return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    reason = reason or "Kicked by Administrator"
    try:
        await bot.ban_chat_member(chat_id, target_id)
        await bot.unban_chat_member(chat_id, target_id)
        target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
        text = (
            f"{emoji_mgr.ban} <b>MEMBER KICKED</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.star} <b>Member:</b> {target_mention} (<code>{target_id}</code>)\n"
            f"{emoji_mgr.error} <b>Reason:</b> {html.escape(reason)}"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error kicking user: {e}"))

@router.message(Command("kick", prefix="/!"))
async def cmd_kick(message: Message, command: CommandObject, bot: Bot):
    await execute_kick(message, bot, command=command)

async def execute_ban(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    target_id, target_name, reason = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please type <code>/banlist</code> to view and unban, or enter User ID (e.g. <code>/ban 123456789</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/ban @masteroogwayv1 [reason]</code> or <code>ban @masteroogwayv1</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    bot_me = await bot.get_me()
    if target_id == bot_me.id:
        err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot ban the bot!"))
        schedule_auto_delete(err_msg, 30)
        return

    if message.reply_to_message and message.reply_to_message.from_user:
        if await is_admin_or_owner(chat_id, message.reply_to_message.from_user, bot, sender_chat=message.reply_to_message.sender_chat):
            err_msg = await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Cannot ban an Administrator!"))
            schedule_auto_delete(err_msg, 30)
            return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    reason = reason or "Banned permanently by Administrator"
    try:
        await bot.ban_chat_member(chat_id, target_id)
        await db.reset_warns(chat_id, target_id)
        u_uname = target_name.lstrip("@") if target_name.startswith("@") else ""
        await db.add_banned_user(chat_id, target_id, u_uname, target_name, reason)
        target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
        text = (
            f"{emoji_mgr.ban} <b>PERMANENTLY BANNED</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.star} <b>Member:</b> {target_mention} (<code>{target_id}</code>)\n"
            f"{emoji_mgr.error} <b>Reason:</b> {html.escape(reason)}\n"
            f"{emoji_mgr.shield} <b>Action:</b> <i>Banned permanently from the group.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Unban Member", callback_data=f"quick_unban:{target_id}")]
        ])
        await safe_answer(message, emoji_mgr.format_msg(text), reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error banning user: {e}"))

@router.message(Command("ban", prefix="/!"))
async def cmd_ban(message: Message, command: CommandObject, bot: Bot):
    await execute_ban(message, bot, command=command)

async def execute_unban(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    target_id, target_name, _ = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please type <code>/banlist</code> to view and unban with 1-click, or enter User ID (e.g. <code>/unban 123456789</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/unban @masteroogwayv1</code> or <code>/unban 123456789</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    try:
        await bot.unban_chat_member(chat_id, target_id)
        await db.reset_warns(chat_id, target_id)
        await db.remove_banned_user(chat_id, target_id)
        target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
        text = (
            f"{emoji_mgr.star} <b>MEMBER UNBANNED</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.star} <b>Member:</b> {target_mention} (<code>{target_id}</code>)\n"
            f"{emoji_mgr.shield} <b>Status:</b> <i>Successfully unbanned and all warnings cleared!</i>"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    except Exception as e:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Error unbanning: {e}"))

@router.message(Command("unban", prefix="/!"))
async def cmd_unban(message: Message, command: CommandObject, bot: Bot):
    await execute_unban(message, bot, command=command)

async def execute_banlist(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    banned_list = await db.get_banned_users(chat_id, limit=30)
    if not banned_list:
        text = f"{emoji_mgr.shield} <b>BANNED MEMBERS LIST</b> {emoji_mgr.vip}\n\nThere are currently no banned members in this group!"
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
        return

    lines = [f"{emoji_mgr.ban} <b>BANNED MEMBERS LIST ({len(banned_list)})</b> {emoji_mgr.vip}\n"]
    buttons = []
    for idx, u in enumerate(banned_list, 1):
        u_id = u["user_id"]
        u_name = u["full_name"] or f"User {u_id}"
        u_uname = f"(@{u['username']})" if u.get("username") else ""
        reason = u.get("reason") or "Rule violation"
        lines.append(f"<b>{idx}.</b> <a href='tg://user?id={u_id}'>{html.escape(u_name)}</a> {html.escape(u_uname)}\n└ ID: <code>{u_id}</code> | Reason: <i>{html.escape(reason)}</i>")
        btn_label = f"🔓 Unban {u['username'] or u_id}"[:30]
        buttons.append([InlineKeyboardButton(text=btn_label, callback_data=f"quick_unban:{u_id}")])

    lines.append(f"\n💡 <i>Click buttons below to unban or type:</i> <code>/unban &lt;ID or @username&gt;</code>")
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_answer(message, emoji_mgr.format_msg("\n".join(lines)), reply_markup=keyboard, parse_mode="HTML")

@router.message(Command("banlist", "banned", prefix="/!"))
async def cmd_banlist(message: Message, bot: Bot):
    await execute_banlist(message, bot)

async def execute_resetwarns(message: Message, bot: Bot, command: Optional[CommandObject] = None, raw_args: str = ""):
    chat_id = message.chat.id
    if message.chat.type == "private":
        return
    if not await require_admin(message, bot):
        return

    target_id, target_name, _ = await resolve_target(message, bot, command, raw_args)
    if not target_id:
        if target_name and target_name.startswith("@"):
            err_txt = f"{emoji_mgr.warn} <b>USERNAME NOT FOUND:</b> No User ID found for {html.escape(target_name)} in group records!\n\n💡 Please reply directly to their message or enter User ID (e.g. <code>/resetwarns 123456789</code>)!"
        else:
            err_txt = f"{emoji_mgr.warn} <b>TARGET REQUIRED:</b> Please enter a @username, User ID, or reply to a message (e.g. <code>/resetwarns @masteroogwayv1</code> or <code>/resetwarns 123456789</code>)!"
        err_msg = await safe_answer(message, emoji_mgr.format_msg(err_txt), parse_mode="HTML")
        schedule_auto_delete(err_msg, 30)
        return

    if target_id and (target_name.startswith("User ") or not target_name):
        try:
            member = await bot.get_chat_member(chat_id, target_id)
            if member and member.user:
                target_name = member.user.full_name
        except Exception:
            pass

    await db.reset_warns(chat_id, target_id)
    target_mention = f"<a href='tg://user?id={target_id}'>{html.escape(target_name)}</a>"
    text = (
        f"{emoji_mgr.star} <b>WARNINGS RESET</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Member:</b> {target_mention} (<code>{target_id}</code>)\n"
        f"{emoji_mgr.warn} <b>Current Warnings:</b> <code>0/5</code>"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("resetwarns", "clearwarns", prefix="/!"))
async def cmd_resetwarns(message: Message, command: CommandObject, bot: Bot):
    await execute_resetwarns(message, bot, command=command)

# -------------------------------------------------------------
# PLAIN TEXT MODERATION COMMAND HANDLER (warn 123, ban 123, etc.)
# -------------------------------------------------------------
@router.message(PlainAdminCommandFilter(), F.chat.type.in_(["group", "supergroup"]))
async def handle_plain_admin_commands(message: Message, bot: Bot, parsed_admin_cmd: tuple[str, str]):
    cmd, args = parsed_admin_cmd
    if cmd == "warn":
        await execute_warn(message, bot, raw_args=args)
    elif cmd == "ban":
        await execute_ban(message, bot, raw_args=args)
    elif cmd == "unwarn":
        await execute_unwarn(message, bot, raw_args=args)
    elif cmd == "unban":
        await execute_unban(message, bot, raw_args=args)
    elif cmd in ["resetwarns", "clearwarns"]:
        await execute_resetwarns(message, bot, raw_args=args)
    elif cmd == "mute":
        await execute_mute(message, bot, raw_args=args)
    elif cmd == "unmute":
        await execute_unmute(message, bot, raw_args=args)
    elif cmd == "kick":
        await execute_kick(message, bot, raw_args=args)
    elif cmd in ["banlist", "banned"]:
        await execute_banlist(message, bot)

# -------------------------------------------------------------
# BANNED WORDS MANAGEMENT (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("addword"))
async def cmd_addword(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if not await require_admin(message, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Usage: <code>/addword [word]</code>"))
        return
    word = command.args.strip().lower()
    success = await db.add_banned_word(chat_id, word, message.from_user.id if message.from_user else 0)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} Added <b>{html.escape(word)}</b> to banned words list!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} This word is already in the blacklist!"))

@router.message(Command("delword"))
async def cmd_delword(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if not await require_admin(message, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Usage: <code>/delword [word]</code>"))
        return
    word = command.args.strip().lower()
    success = await db.remove_banned_word(chat_id, word)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} Removed <b>{html.escape(word)}</b> from blacklist!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Word not found in blacklist!"))

@router.message(Command("listwords"))
async def cmd_listwords(message: Message, bot: Bot):
    chat_id = message.chat.id
    if not await require_admin(message, bot):
        return
    words = await db.get_banned_words(chat_id)
    if not words:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.shield} Using default global blacklist."))
        return
    words_str = ", ".join([f"<code>{html.escape(w)}</code>" for w in words[:50]])
    text = f"{emoji_mgr.shield} <b>BANNED WORDS LIST ({len(words)} words):</b> {emoji_mgr.vip}\n\n{words_str}"
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

# -------------------------------------------------------------
# WHITELIST LINK MANAGEMENT (ADMIN ONLY)
# -------------------------------------------------------------
@router.message(Command("addlink"))
async def cmd_addlink(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if not await require_admin(message, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Usage: <code>/addlink [domain]</code> (e.g. <code>/addlink youtube.com</code>)"))
        return
    domain = command.args.strip().lower()
    success = await db.add_whitelist_link(chat_id, domain)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} Added <b>{html.escape(domain)}</b> to whitelist!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Domain is already in whitelist!"))

@router.message(Command("dellink"))
async def cmd_dellink(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id
    if not await require_admin(message, bot):
        return
    if not command.args:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.warn} Usage: <code>/dellink [domain]</code>"))
        return
    domain = command.args.strip().lower()
    success = await db.remove_whitelist_link(chat_id, domain)
    if success:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.star} Removed <b>{html.escape(domain)}</b> from whitelist!"), parse_mode="HTML")
    else:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Domain not found in whitelist!"))

@router.message(Command("listlinks"))
async def cmd_listlinks(message: Message, bot: Bot):
    chat_id = message.chat.id
    if not await require_admin(message, bot):
        return
    links = await db.get_whitelist_links(chat_id)
    if not links:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.link} Link whitelist is empty (all external links blocked)."))
        return
    links_str = "\n".join([f"{emoji_mgr.link} <code>{html.escape(l)}</code>" for l in links])
    text = f"{emoji_mgr.link} <b>WHITELISTED DOMAINS ({len(links)}):</b> {emoji_mgr.vip}\n\n{links_str}"
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
            f"{emoji_mgr.warn} <b>NO CUSTOM EMOJI FOUND!</b> {emoji_mgr.vip}\n\n"
            f"💡 <b>Instructions:</b>\n"
            f"{emoji_mgr.star} 1. Send a message containing your Telegram Premium animated custom emojis.\n"
            f"{emoji_mgr.star} 2. Reply to that message and type: <code>/get_emoji</code>\n"
            f"{emoji_mgr.star} Or send <code>/get_emoji</code> with VIP emojis in the same message.\n\n"
            f"The bot will extract the custom emoji ID for configuration!"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
        return

    output_lines = [f"{emoji_mgr.vip} <b>FOUND {len(found_emojis)} TELEGRAM PREMIUM CUSTOM EMOJIS:</b>\n"]
    for idx, (emoji_id, char) in enumerate(found_emojis, 1):
        output_lines.append(
            f"<b>#{idx}</b> <tg-emoji emoji-id='{emoji_id}'>{char}</tg-emoji>\n"
            f"{emoji_mgr.star} <b>Emoji ID:</b> <code>{emoji_id}</code>\n"
            f"{emoji_mgr.star} <b>Set command:</b> <code>/set_emoji vip {emoji_id}</code>\n"
        )
    output_lines.append(f"\n{emoji_mgr.diamond} <i>You can use /set_emoji [key] [id] to apply changes immediately!</i>")
    await safe_answer(message, emoji_mgr.format_msg("\n".join(output_lines)), parse_mode="HTML")

@router.message(Command("set_emoji", "setemoji"))
async def cmd_set_emoji(message: Message, command: CommandObject, bot: Bot):
    if not await require_admin(message, bot):
        return

    if not command.args:
        text = (
            f"{emoji_mgr.settings} <b>VIP CUSTOM EMOJI SETTINGS</b> {emoji_mgr.vip}\n\n"
            f"Usage: <code>/set_emoji [key] [emoji_id] [fallback_char]</code>\n"
            f"Example: <code>/set_emoji vip 5217822164362739968 👑</code>\n\n"
            f"<b>Valid keys:</b>\n"
            f"<code>vip</code>, <code>shield</code>, <code>warn</code>, <code>ban</code>, <code>mute</code>, <code>link</code>, <code>spam</code>, <code>clock</code>, <code>tele_logo</code>, <code>error</code>, <code>diamond</code>, <code>star</code>, <code>bell</code>, <code>settings</code>"
        )
        await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
        return

    parts = command.args.split()
    if len(parts) < 2:
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Please provide both [key] and [emoji_id]!"))
        return

    key = parts[0].lower().strip()
    emoji_id = parts[1].strip()
    fallback = parts[2].strip() if len(parts) > 2 else "✨"

    if not emoji_id.isdigit():
        await safe_answer(message, emoji_mgr.format_msg(f"{emoji_mgr.error} Emoji ID must be a valid integer string!"))
        return

    await db.set_custom_emoji(key, emoji_id, fallback)
    await emoji_mgr.load_emojis()

    text = (
        f"{emoji_mgr.star} Custom Emoji for key <b>{html.escape(key)}</b> updated successfully! {emoji_mgr.vip}\n"
        f"{emoji_mgr.star} Preview: <tg-emoji emoji-id='{emoji_id}'>{fallback}</tg-emoji> (ID: <code>{emoji_id}</code>)"
    )
    await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")

@router.message(Command("list_emojis", "listemojis"))
async def cmd_list_emojis(message: Message, bot: Bot):
    if not await require_admin(message, bot):
        return

    await emoji_mgr.load_emojis()
    lines = [f"{emoji_mgr.vip} <b>CURRENT ACTIVE CUSTOM EMOJI KEYS:</b>\n"]

    all_keys = ["tele_logo", "clock", "vip", "shield", "warn", "ban", "mute", "link", "spam", "error", "settings", "diamond", "star", "bell"]
    for k in all_keys:
        icon_rendered = emoji_mgr.get(k)
        conf_id = config.DEFAULT_EMOJIS.get(k, {}).get("id", "")
        db_val = emoji_mgr._db_emojis.get(k, {}).get("id")
        current_id = db_val if db_val else (conf_id if conf_id else "No ID assigned")
        lines.append(f"{emoji_mgr.star} <b>{k.upper()}:</b> {icon_rendered} | ID: <code>{current_id}</code>")

    await safe_answer(message, emoji_mgr.format_msg("\n".join(lines)), parse_mode="HTML")

@router.message(Command("test_emoji", "testemoji"))
async def cmd_test_emoji(message: Message, command: CommandObject, bot: Bot):
    if not await require_admin(message, bot):
        return

    if not command.args:
        results = []
        for k, val in config.DEFAULT_EMOJIS.items():
            eid = val.get("id", "")
            fb = val.get("fallback", "✨")
            if eid:
                results.append(f"• <b>{k.upper()}:</b> <tg-emoji emoji-id='{eid}'>{fb}</tg-emoji> | ID: <code>{eid}</code>")
        text = "<b>TEST CUSTOM EMOJI DISPLAY:</b>\n\n" + "\n".join(results)
        await message.answer(text, parse_mode="HTML")
        return

    arg = command.args.strip()
    if arg.isdigit():
        eid = arg
        test_txt = f"Test Emoji ID <code>{eid}</code>: <tg-emoji emoji-id='{eid}'>✨</tg-emoji>"
    else:
        k = arg.lower()
        eid = config.DEFAULT_EMOJIS.get(k, {}).get("id", "")
        test_txt = f"Test Key <b>{k}</b>: {emoji_mgr.get(k)} | ID: <code>{eid}</code>"
    try:
        await message.answer(test_txt, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Telegram API rejected this emoji: {e}", parse_mode="HTML")

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

    text = (
        f"{emoji_mgr.shield} <b>GROUP SECURITY STATISTICS</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} {emoji_mgr.spam} <b>Spam & Flood blocked:</b> <code>{spam_count}</code>\n"
        f"{emoji_mgr.star} {emoji_mgr.link} <b>Unauthorized Links removed:</b> <code>{link_count}</code>\n"
        f"{emoji_mgr.star} {emoji_mgr.error} <b>Profanity filtered:</b> <code>{badwords_count}</code>\n"
        f"{emoji_mgr.star} {emoji_mgr.shield} <b>Unauthorized Bots blocked:</b> <code>{bot_count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.diamond} <b>Total violations prevented:</b> <code>{total}</code>"
    )
    sent_msg = await safe_answer(message, emoji_mgr.format_msg(text), parse_mode="HTML")
    if not is_private:
        settings = await db.get_chat_settings(chat_id)
        if settings.get("auto_delete_logs", 1):
            schedule_auto_delete(sent_msg, config.AUTO_DELETE_LOGS_SEC)
