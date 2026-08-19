import asyncio
import html
from aiogram import Router, F, Bot
from aiogram.types import ChatMemberUpdated, Message, ChatPermissions
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, KICKED, LEFT, RESTRICTED
from database.db import db
from utils.emoji_helper import emoji_mgr, safe_send_message, safe_answer
from utils.logger import logger
import config

router = Router(name="member_handlers")

async def is_user_admin(chat_id: int, user_id: int, bot: Bot) -> bool:
    """Checks if a user is an administrator or owner in the group"""
    if user_id in config.OWNER_IDS:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

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

    # Check if the joined member is a BOT
    if new_user.is_bot:
        bot_info = await bot.get_me()
        if new_user.id == bot_info.id:
            logger.info("Bot added to group %s (%s)", event.chat.title, chat_id)
            return

        settings = await db.get_chat_settings(chat_id)
        if settings.get("anti_bot", 1):
            inviter_id = inviter.id if inviter else 0
            is_admin = await is_user_admin(chat_id, inviter_id, bot) if inviter_id else False

            if not is_admin:
                try:
                    # 1. Ban/Kick the unauthorized bot immediately
                    await bot.ban_chat_member(chat_id, new_user.id)
                    await db.increment_stat(chat_id, "bot_blocked")

                    # 2. Build VIP notification message
                    inviter_name = html.escape(inviter.full_name) if inviter else "Không rõ"
                    inviter_mention = f"<a href='tg://user?id={inviter.id}'>{inviter_name}</a>" if inviter else "Không rõ"
                    bot_name = html.escape(new_user.full_name)
                    bot_username = f"@{new_user.username}" if new_user.username else f"ID: {new_user.id}"

                    alert_text = (
                        f"{emoji_mgr.shield} <b>BẢO VỆ NHÓM - CHẶN BOT LẠ</b> {emoji_mgr.vip}\n\n"
                        f"{emoji_mgr.bot} <b>Bot bị phát hiện:</b> {bot_name} ({bot_username})\n"
                        f"{emoji_mgr.warn} <b>Người thêm:</b> {inviter_mention}\n"
                        f"{emoji_mgr.ban} <b>Hành động:</b> <i>Đã tự động trục xuất bot trái phép!</i>\n\n"
                        f"{emoji_mgr.diamond} <i>Chỉ có Quản trị viên mới được phép thêm bot vào nhóm.</i>"
                    )
                    final_text = emoji_mgr.format_msg(alert_text)
                    msg = await safe_send_message(bot, chat_id, final_text, parse_mode="HTML")

                    # Auto-delete notification after 30s
                    if settings.get("auto_delete_logs", 1):
                        await asyncio.sleep(config.AUTO_DELETE_LOGS_SEC)
                        try:
                            await msg.delete()
                        except Exception:
                            pass

                except Exception as e:
                    logger.error("Failed to kick unauthorized bot %s: %s", new_user.id, e)

@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot):
    """
    Fallback handler for new chat members message
    """
    chat_id = message.chat.id
    if message.chat.type not in ["group", "supergroup"]:
        return

    settings = await db.get_chat_settings(chat_id)
    if not settings.get("anti_bot", 1):
        return

    bot_info = await bot.get_me()
    inviter = message.from_user
    inviter_id = inviter.id if inviter else 0
    is_admin = await is_user_admin(chat_id, inviter_id, bot) if inviter_id else False

    for member in message.new_chat_members:
        if member.is_bot and member.id != bot_info.id:
            if not is_admin:
                try:
                    await bot.ban_chat_member(chat_id, member.id)
                    await db.increment_stat(chat_id, "bot_blocked")
                    
                    try:
                        await message.delete()
                    except Exception:
                        pass

                    inviter_name = html.escape(inviter.full_name) if inviter else "Không rõ"
                    inviter_mention = f"<a href='tg://user?id={inviter_id}'>{inviter_name}</a>" if inviter else "Không rõ"

                    alert_text = (
                        f"{emoji_mgr.shield} <b>PHÒNG THỦ NHÓM - CHẶN BOT</b> {emoji_mgr.vip}\n\n"
                        f"{emoji_mgr.bot} <b>Bot:</b> {html.escape(member.full_name)}\n"
                        f"{emoji_mgr.warn} <b>Người thêm:</b> {inviter_mention}\n"
                        f"{emoji_mgr.ban} <b>Xử lý:</b> <i>Đã kick bot thành công!</i>"
                    )
                    final_text = emoji_mgr.format_msg(alert_text)
                    sent = await safe_answer(message, final_text, parse_mode="HTML")
                    if settings.get("auto_delete_logs", 1):
                        await asyncio.sleep(config.AUTO_DELETE_LOGS_SEC)
                        try:
                            await sent.delete()
                        except Exception:
                            pass
                except Exception as e:
                    logger.error("Error auto-kicking bot: %s", e)
