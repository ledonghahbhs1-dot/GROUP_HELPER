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
    1. Sends evidence request message in English with icon
    2. Forwards the message to admin @wolfmodyt
    """
    text = message.text or message.caption or ""
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id
    user_name = user.full_name

    # Don't delete the message yet - show evidence request first
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

    # Evidence request message with icon
    evidence_text = (
        f"{emoji_mgr.shield} <b>⚠️ SCAM / FRAUD ALERT</b> {emoji_mgr.warn}\n\n"
        f"{emoji_mgr.bell} <b>Member:</b> {user_mention}\n"
        f"{emoji_mgr.error} <b>Detected Keyword:</b> <code>{html.escape(matched_keyword)}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.star} <b>🚨 IMPORTANT NOTICE 🚨</b>\n\n"
        f"This message may contain <b>scam/fraud content</b>.\n\n"
        f"{emoji_mgr.warn} <b>IF YOU ARE A VICTIM:</b>\n"
        f"• Please provide <b>EVIDENCE</b> by replying to this message\n"
        f"• Screenshots, transaction IDs, chat history, or any proof\n"
        f"• This information will be forwarded to administrators for review\n\n"
        f"{emoji_mgr.vip} <b>FOR ADMINS & GROUP MEMBERS:</b>\n"
        f"• Report suspicious messages with evidence\n"
        f"• Help us protect the community from scammers\n"
        f"• Contact: <b>@wolfmodyt</b> with proofs\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji_mgr.lock} <b>Message forwarded to administrators for investigation.</b>"
    )

    try:
        # Send evidence request message (visible to all)
        sent_alert = await safe_send_message(
            bot,
            chat_id,
            emoji_mgr.format_msg(evidence_text),
            parse_mode="HTML"
        )
        # Auto-delete after 2 minutes
        if sent_alert:
            schedule_auto_delete(sent_alert, 120)
    except Exception as e:
        logger.error(f"Failed to send scam alert in chat {chat_id}: {e}")

    # Forward original message to admin/owner
    try:
        admin_forward_text = (
            f"{emoji_mgr.warn} <b>🚨 SCAM DETECTION REPORT 🚨</b> {emoji_mgr.warn}\n\n"
            f"{emoji_mgr.shield} <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"{emoji_mgr.shield} <b>User ID:</b> <code>{user_id}</code>\n"
            f"{emoji_mgr.shield} <b>Username:</b> @{user.username or 'N/A'}\n"
            f"{emoji_mgr.shield} <b>Name:</b> {html.escape(user_name)}\n\n"
            f"{emoji_mgr.error} <b>Matched Keyword:</b> <code>{html.escape(matched_keyword)}</code>\n"
            f"{emoji_mgr.error} <b>Original Message:</b>\n<code>{html.escape(text[:500])}</code>\n\n"
            f"{emoji_mgr.star} <b>Action Required:</b> Review and verify if this is a real scam\n"
            f"{emoji_mgr.star} <b>Forward:</b> <a href='tg://user?id={user_id}'>Contact User</a>"
        )

        # Send to owner
        for owner_id in config.OWNER_IDS:
            try:
                await safe_send_message(
                    bot,
                    owner_id,
                    emoji_mgr.format_msg(admin_forward_text),
                    parse_mode="HTML"
                )

                # Try to forward original message as well
                try:
                    await bot.forward_message(
                        chat_id=owner_id,
                        from_chat_id=chat_id,
                        message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Could not forward message to admin {owner_id}: {e}")

            except Exception as e:
                logger.error(f"Failed to send scam report to owner {owner_id}: {e}")

    except Exception as e:
        logger.error(f"Failed to handle scam message: {e}")

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
