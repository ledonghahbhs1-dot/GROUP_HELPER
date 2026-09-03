import asyncio
import html
import time
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatPermissions, MessageOriginUser
from database.db import db
from utils.emoji_helper import emoji_mgr, safe_answer, safe_send_message, schedule_auto_delete, get_payment_info_text, get_script_tool_info_text, get_issue_support_text
from utils.auth import is_user_allowed_private, is_admin_or_owner
from utils.logger import logger
from filters.spam_filter import spam_filter
from filters.link_filter import link_filter
from filters.profanity_filter import profanity_filter
from filters.payment_filter import payment_detector
from filters.script_filter import script_detector
from filters.issue_filter import issue_detector
from filters.scam_filter import scam_detector
import config

router = Router(name="message_handlers")

def check_bot_forward(message: Message) -> tuple[bool, str]:
    """Check if message is forwarded from a bot or sent via an inline bot"""
    # 1. aiogram 3.x MessageOrigin
    if message.forward_origin:
        if isinstance(message.forward_origin, MessageOriginUser) and message.forward_origin.sender_user.is_bot:
            bot_user = message.forward_origin.sender_user
            bot_handle = f"@{bot_user.username}" if bot_user.username else (bot_user.full_name or "Bot")
            return True, f"Forwarded message from bot ({bot_handle})"

    # 2. Legacy forward_from
    if getattr(message, "forward_from", None) and message.forward_from.is_bot:
        bot_user = message.forward_from
        bot_handle = f"@{bot_user.username}" if bot_user.username else (bot_user.full_name or "Bot")
        return True, f"Forwarded message from bot ({bot_handle})"

    # 3. Via inline bot
    if getattr(message, "via_bot", None) and message.via_bot:
        bot_user = message.via_bot
        bot_handle = f"@{bot_user.username}" if bot_user.username else (bot_user.full_name or "Bot")
        return True, f"Sent via inline bot ({bot_handle})"

    return False, ""

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
            await db.add_banned_user(chat_id, user_id, "", user_name, reason)
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
    Direct message handler:
    - Responds to payment queries, script queries, and issue reports from ANY user.
    - Greets Master @wolfmodyt with full status menu.
    - Silently ignores other unauthorized DM messages.
    """
    user = message.from_user
    user_id = user.id if user else 0
    text = message.text or message.caption or ""

    # 1. Check Issue / Not Working query
    if text and issue_detector.is_issue_query(text)[0]:
        text_issue = get_issue_support_text(user_id, user.full_name if user else "")
        await safe_answer(message, emoji_mgr.format_msg(text_issue), parse_mode="HTML")
        return

    # 2. Check Payment query (pay, payment, bank, stk, etc.)
    if text and payment_detector.is_payment_query(text):
        text_pay = get_payment_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_pay), parse_mode="HTML", disable_web_page_preview=True)
        return

    # 3. Check Script / Tool query (script, tool, key, dc, etc.)
    if text and script_detector.is_script_query(text):
        text_script = get_script_tool_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_script), parse_mode="HTML", disable_web_page_preview=True)
        return

    # Check authorization for other direct bot messages
    if not is_user_allowed_private(user):
        user_info = f"ID: {user.id}, Username: @{user.username}" if user else "Unknown"
        logger.info("Private message silently ignored from unauthorized user (%s)", user_info)
        return

    logger.info("Private message received from authorized user @%s (%s)", user.username, user.id)

    # Direct message response in English for @wolfmodyt
    reply_text = (
        f"{emoji_mgr.shield} <b>HELLO MASTER @wolfmodyt!</b> {emoji_mgr.vip}\n\n"
        f"Your Group Security & Anti-Spam Guard Bot is operational:\n"
        f"{emoji_mgr.star} Add the bot to your group and grant Administrator permissions to activate defense.\n"
        f"{emoji_mgr.star} In group chats, the bot will moderate in <b>English</b> and delete offending messages.\n"
        f"{emoji_mgr.star} Type <code>/pay</code> or <code>pay</code> to view Payment Methods.\n"
        f"{emoji_mgr.star} Type <code>/help</code> to view all group management commands."
    )
    await safe_answer(message, emoji_mgr.format_msg(reply_text), parse_mode="HTML")

@router.message(F.chat.type.in_(["group", "supergroup"]))
async def inspect_message(message: Message, bot: Bot):
    """
    Main moderation pipeline for group messages (in English)
    """
    text = message.text or message.caption or ""
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id if user else 0
    logger.info("GROUP MSG [%s in %s (%s)]: text=%r", user_id, chat_id, message.chat.type, text)

    # Cache user for @username command resolution
    if user and not user.is_bot:
        try:
            await db.save_user(user.id, user.username or "", user.full_name or "")
        except Exception:
            pass

    # 1. 100% Exempt Anonymous Admins, Group Senders & Channel Senders from MODERATION
    is_sender_exempt = False
    if message.sender_chat is not None:
        is_sender_exempt = True
    elif user and (user.id in [1087968824, 777000] or getattr(user, "username", "") == "GroupAnonymousBot"):
        is_sender_exempt = True
    elif not user or user.is_bot:
        is_sender_exempt = True
    elif await is_admin_or_owner(chat_id, user, bot, sender_chat=message.sender_chat):
        is_sender_exempt = True

    # If sender is an Admin / Owner / Channel / Bot:
    if is_sender_exempt:
        # Check if they queried issue, payment or script
        if text and issue_detector.is_issue_query(text)[0]:
            text_issue = get_issue_support_text(user_id, user.full_name if user else "")
            await safe_answer(message, emoji_mgr.format_msg(text_issue), parse_mode="HTML")
            return
        if text and payment_detector.is_payment_query(text):
            text_pay = get_payment_info_text()
            await safe_answer(message, emoji_mgr.format_msg(text_pay), parse_mode="HTML", disable_web_page_preview=True)
            return
        if text and script_detector.is_script_query(text):
            text_script = get_script_tool_info_text()
            await safe_answer(message, emoji_mgr.format_msg(text_script), parse_mode="HTML", disable_web_page_preview=True)
            return
        return

    # -------------------------------------------------------------
    # BELOW THIS LINE: MODERATION FOR REGULAR MEMBERS
    # -------------------------------------------------------------

    # 5. Check Scam/Fraud/Spam Accusation Detection (HIGHEST PRIORITY)
    if text:
        is_scam, matched_keyword = scam_detector.is_scam_message(text)
        if is_scam:
            user_name = user.full_name
            user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
            evidence_text = (
                f"{emoji_mgr.shield} <b>SECURITY ALERT - EVIDENCE REQUIRED</b> {emoji_mgr.vip}\n\n"
                f"{emoji_mgr.bell} <b>User:</b> {user_mention} (<code>{user_id}</code>)\n"
                f"{emoji_mgr.warn} <b>Detected Keyword:</b> <code>{html.escape(matched_keyword)}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{emoji_mgr.star} <b>PLEASE PROVIDE EVIDENCE</b>\n\n"
                f"• If you are reporting scam, spam, or abuse, please reply to this message with <b>screenshots, transaction IDs, links, or proof</b>.\n"
                f"• Describe what happened in detail so administrators can review.\n\n"
                f"{emoji_mgr.diamond} <b>If this is a false alarm / normal conversation:</b>\n"
                f"• Please clarify the context.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{emoji_mgr.vip} <b>Contact Admin:</b> @wolfmodyt"
            )
            # DO NOT delete user's message (as requested), reply with English evidence request + VIP icons
            try:
                await safe_answer(message, emoji_mgr.format_msg(evidence_text), parse_mode="HTML")
                logger.info(f"Evidence request sent to user {user_id} in chat {chat_id} (keyword: {matched_keyword})")
            except Exception as e:
                logger.error(f"Failed to reply evidence request: {e}")

            # Forward original message + report to admin
            if config.OWNER_IDS and len(config.OWNER_IDS) > 0 and config.OWNER_IDS[0] > 0:
                try:
                    for owner_id in config.OWNER_IDS:
                        if owner_id > 0:
                            admin_text = (
                                f"{emoji_mgr.warn} <b>SCAM DETECTION REPORT</b> {emoji_mgr.warn}\n\n"
                                f"{emoji_mgr.shield} <b>Chat ID:</b> <code>{chat_id}</code>\n"
                                f"{emoji_mgr.shield} <b>User ID:</b> <code>{user_id}</code>\n"
                                f"{emoji_mgr.shield} <b>Username:</b> @{user.username or 'N/A'}\n"
                                f"{emoji_mgr.shield} <b>Name:</b> {html.escape(user_name)}\n"
                                f"{emoji_mgr.shield} <b>Matched Keyword:</b> <code>{html.escape(matched_keyword)}</code>\n"
                                f"{emoji_mgr.error} <b>Message Preview:</b> <code>{html.escape(text[:300])}</code>"
                            )
                            await safe_send_message(bot, owner_id, emoji_mgr.format_msg(admin_text), parse_mode="HTML")
                            logger.info(f"Scam report sent to admin {owner_id}")

                            try:
                                await bot.forward_message(
                                    chat_id=owner_id,
                                    from_chat_id=chat_id,
                                    message_id=message.message_id
                                )
                                logger.info(f"Original scam message forwarded to admin {owner_id}")
                            except Exception as fw_error:
                                logger.warning(f"Could not forward original message to admin {owner_id}: {fw_error}")
                except Exception as e:
                    logger.warning(f"Failed to send scam report to admin: {e}")

            # Log violation
            try:
                await db.increment_stat(chat_id, "scam")
            except:
                pass
            return

    # Load group settings
    settings = await db.get_chat_settings(chat_id)
    violation_type = None
    violation_desc = ""

    # -------------------------------------------------------------
    # 1. Check Anti-Bot Forward / Inline Bot (anti_bot)
    # -------------------------------------------------------------
    if settings.get("anti_bot", 1):
        is_bot_fwd, bot_fwd_desc = check_bot_forward(message)
        if is_bot_fwd:
            violation_type = "bot"
            violation_desc = f"Bot Forward / Inline Bot [{html.escape(bot_fwd_desc)}]"
            await db.increment_stat(chat_id, "bot_blocked")

    # -------------------------------------------------------------
    # 2. Check Anti-Badwords / Toxicity
    # -------------------------------------------------------------
    if not violation_type and settings.get("anti_badwords", 1) and text:
        is_profane, matched_word = await profanity_filter.check_profanity(text, chat_id)
        if is_profane:
            violation_type = "badwords"
            violation_desc = f"Profanity / Inappropriate language [<code>{html.escape(matched_word)}</code>]"
            await db.increment_stat(chat_id, "badwords")

    # -------------------------------------------------------------
    # 3. Check Anti-Link & Bot Link Detection
    # -------------------------------------------------------------
    if not violation_type and (settings.get("anti_link", 1) or settings.get("anti_bot", 1)):
        bot_info = await bot.get_me()
        has_link, link_desc, is_bot = await link_filter.check_links(message, chat_id, own_bot_username=bot_info.username or "")
        if has_link:
            if is_bot:
                violation_type = "bot_link"
                violation_desc = f"Unauthorized External Bot Link [<code>{html.escape(link_desc)}</code>]"
                await db.increment_stat(chat_id, "bot_blocked")
            elif settings.get("anti_link", 1):
                violation_type = "link"
                violation_desc = f"Unauthorized External Link [<code>{html.escape(link_desc)}</code>]"
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
    # Handle Violation in Group (Immediate delete user msg + permanent warning)
    # -------------------------------------------------------------
    if violation_type:
        # Delete offending user message immediately
        try:
            await message.delete()
            logger.info("Deleted offending %s message (ID: %s) from user %s in chat %s", violation_type, message.message_id, user_id, chat_id)
        except Exception as del_err:
            logger.warning("Failed to delete offending message %s from user %s: %s", message.message_id, user_id, del_err)

        max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS) # Default = 5
        warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION) # Default = 'ban'
        mute_dur = settings.get("mute_duration", config.DEFAULT_MUTE_DURATION)

        # Add warning count
        current_warns = await db.add_warn(chat_id, user_id, violation_desc)
        user_name = user.full_name
        user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

        # Check if max warns reached (Quá max_warns lần sẽ bị BAN vĩnh viễn khỏi group chat)
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
                f"{emoji_mgr.warn} <b>Member:</b> {user_mention} (<code>{user_id}</code>)\n"
                f"{emoji_mgr.ban} <b>Reason:</b> {violation_desc}\n"
                f"{emoji_mgr.error} <b>Warnings:</b> <code>{current_warns}/{max_warns}</code> (MAX REACHED)\n\n"
                f"{punish_msg}"
            )
        else:
            alert_text = (
                f"{emoji_mgr.shield} <b>SECURITY WARNING ({current_warns}/{max_warns})</b> {emoji_mgr.vip}\n\n"
                f"{emoji_mgr.warn} <b>Member:</b> {user_mention} (<code>{user_id}</code>)\n"
                f"{emoji_mgr.error} <b>Violation:</b> {violation_desc}\n"
                f"{emoji_mgr.bell} <b>Action:</b> Offending message has been deleted immediately.\n"
                f"{emoji_mgr.star} <b>Warning Count:</b> <code>{current_warns}/{max_warns}</code>\n\n"
                f"{emoji_mgr.diamond} <i>Maximum {max_warns} warnings allowed. Exceeding {max_warns} warnings will result in a permanent BAN!</i>"
            )

        # Append signature
        final_text = emoji_mgr.format_msg(alert_text)

        try:
            # Send warning alert message without auto-deletion (kept permanent in chat)
            await safe_send_message(bot, chat_id, final_text, parse_mode="HTML")
            logger.info("Sent permanent security warning alert to chat %s for user %s", chat_id, user_id)
        except Exception as e:
            logger.error("Failed to send warning alert in chat %s: %s", chat_id, e)
        return

    # -------------------------------------------------------------
    # 8. Check Issue / Not Working / No Effect Queries (HIGHEST SUPPORT PRIORITY)
    # -------------------------------------------------------------
    if text:
        is_issue, matched_issue_kw = issue_detector.is_issue_query(text)
        if is_issue:
            logger.info("Issue / not-working query detected from member %s: kw=%r, text=%r", user_id, matched_issue_kw, text)
            text_issue = get_issue_support_text(user_id, user.full_name if user else "")
            await safe_answer(message, emoji_mgr.format_msg(text_issue), parse_mode="HTML")
            return

    # -------------------------------------------------------------
    # 9. Check Payment & Script Queries for regular members (Clean message)
    # -------------------------------------------------------------
    if text and payment_detector.is_payment_query(text):
        logger.info("Payment query detected from member: %r", text)
        text_pay = get_payment_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_pay), parse_mode="HTML", disable_web_page_preview=True)
        return

    if text and script_detector.is_script_query(text):
        logger.info("Script query detected from member: %r", text)
        text_script = get_script_tool_info_text()
        await safe_answer(message, emoji_mgr.format_msg(text_script), parse_mode="HTML", disable_web_page_preview=True)
        return
