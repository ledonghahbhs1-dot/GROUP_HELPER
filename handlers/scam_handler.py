import html
from aiogram import Router, F, Bot
from aiogram.types import Message, User
from database.db import db
from utils.emoji_helper import emoji_mgr, safe_answer, safe_send_message, schedule_auto_delete
from utils.auth import is_admin_or_owner
from utils.logger import logger
from filters.scam_filter import scam_detector
import config

router = Router(name="scam_handlers")

async def handle_scam_message(
    message: Message,
    bot: Bot,
    matched_keyword: str
):
    """
    Handles detected scam/fraud messages:
    1. Reply to user with evidence request (English) - DO NOT DELETE user message
    2. Include user ID in the message
    3. Forward to admin if OWNER_IDS valid
    """
    text = message.text or message.caption or ""
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id
    user_name = user.full_name

    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

    # Evidence request message - ENGLISH with VIP emoji icons
    evidence_text = (
        f"{emoji_mgr.shield} <b>SCAM / FRAUD ALERT</b> {emoji_mgr.warn}\n\n"
        f"{emoji_mgr.bell} <b>User ID:</b> <code>{user_id}</code>\n"
        f"{emoji_mgr.bell} <b>Member:</b> {user_mention}\n"
        f"{emoji_mgr.error} <b>Detected Keyword:</b> <code>{html.escape(matched_keyword)}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.star} <b>PLEASE PROVIDE EVIDENCE</b>\n\n"
        f"Your message contains a scam-related keyword: <b>{html.escape(matched_keyword)}</b>\n\n"
        f"<b>If you are reporting a REAL SCAM:</b>\n"
        f"• Reply to this message with EVIDENCE\n"
        f"• Provide screenshots, transaction IDs, or proof\n"
        f"• Describe what happened in detail\n"
        f"• This information will be reviewed by administrators\n\n"
        f"<b>If this is a FALSE ALARM:</b>\n"
        f"• Please explain the context\n"
        f"• Administrators will review and determine if action is needed\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.vip} <b>Contact Admin:</b> @wolfmodyt\n"
        f"{emoji_mgr.lock} <b>Status:</b> Report forwarded to administrators"
    )

    try:
        # Reply to user's message (do NOT delete user message)
        await safe_answer(
            message,
            emoji_mgr.format_msg(evidence_text),
            parse_mode="HTML"
        )
        logger.info(f"Scam alert replied to user {user_id} in chat {chat_id} with keyword '{matched_keyword}'")
    except Exception as e:
        logger.error(f"Failed to reply to user {user_id} in chat {chat_id}: {e}")

    # Forward original message to admin/owner (if valid OWNER_IDS configured)
    if config.OWNER_IDS and len(config.OWNER_IDS) > 0 and config.OWNER_IDS[0] > 0:
        try:
            admin_forward_text = (
                f"{emoji_mgr.warn} <b>SCAM DETECTION REPORT</b> {emoji_mgr.warn}\n\n"
                f"{emoji_mgr.shield} <b>Chat ID:</b> <code>{chat_id}</code>\n"
                f"{emoji_mgr.shield} <b>User ID:</b> <code>{user_id}</code>\n"
                f"{emoji_mgr.shield} <b>Username:</b> @{user.username or 'N/A'}\n"
                f"{emoji_mgr.shield} <b>Name:</b> {html.escape(user_name)}\n\n"
                f"{emoji_mgr.error} <b>Matched Keyword:</b> <code>{html.escape(matched_keyword)}</code>\n"
                f"{emoji_mgr.error} <b>Original Message:</b>\n<code>{html.escape(text[:500])}</code>\n\n"
                f"{emoji_mgr.star} <b>Action:</b> Evidence requested from user\n"
                f"{emoji_mgr.star} <b>Contact User:</b> <a href='tg://user?id={user_id}'>@{user.username or 'User'}</a>"
            )

            # Send to owner
            for owner_id in config.OWNER_IDS:
                if owner_id <= 0:
                    continue

                try:
                    await safe_send_message(
                        bot,
                        owner_id,
                        emoji_mgr.format_msg(admin_forward_text),
                        parse_mode="HTML"
                    )
                    logger.info(f"Scam report sent to admin {owner_id}")

                    # Try to forward original message as well
                    try:
                        await bot.forward_message(
                            chat_id=owner_id,
                            from_chat_id=chat_id,
                            message_id=message.message_id
                        )
                        logger.info(f"Original message forwarded to admin {owner_id}")
                    except Exception as e:
                        logger.debug(f"Could not forward original message to admin {owner_id}: {e}")

                except Exception as e:
                    logger.warning(f"Failed to send scam report to admin {owner_id}: {e}")

        except Exception as e:
            logger.error(f"Error in admin notification: {e}")
    else:
        logger.warning(f"OWNER_IDS not configured or invalid. Scam report not sent to admin. Configure OWNER_IDS in config.py")

    # Log the violation
    try:
        await db.increment_stat(chat_id, "scam")
    except Exception as e:
        logger.error(f"Failed to log scam statistic: {e}")


@router.message(F.chat.type.in_(["group", "supergroup"]))
async def detect_scam_messages(message: Message, bot: Bot):
    """
    Check for scam/fraud keywords in group messages
    """
    text = message.text or message.caption or ""

    # Skip if empty
    if not text:
        return

    # Skip if sender is anonymous/admin
    if message.sender_chat is not None:
        return

    user = message.from_user
    if not user or user.is_bot:
        return

    # Skip if user is admin
    chat_id = message.chat.id
    if await is_admin_or_owner(chat_id, user, bot, sender_chat=message.sender_chat):
        return

    # Check for scam keywords
    is_scam, matched_keyword = scam_detector.is_scam_message(text)

    if is_scam:
        logger.warning(
            f"Scam detected in chat {chat_id} from user {user.id}: keyword='{matched_keyword}'",
        )
        await handle_scam_message(message, bot, matched_keyword)
