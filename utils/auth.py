from aiogram import Bot
from typing import Optional
import config

def is_user_allowed_private(user) -> bool:
    """Checks if the user is @wolfmodyt or in OWNER_IDS"""
    if not user:
        return False
    if user.id in config.OWNER_IDS:
        return True
    if user.username:
        clean_uname = user.username.strip().lower().lstrip("@")
        allowed_list = [u.strip().lower().lstrip("@") for u in config.ALLOWED_PRIVATE_USERNAMES]
        if clean_uname in allowed_list:
            return True
    return False

async def is_admin_or_owner(chat_id: int, user, bot: Bot) -> bool:
    """
    Checks if a user is @wolfmodyt, an owner, or a group administrator.
    Gives @wolfmodyt full master rights everywhere.
    """
    if not user:
        return False
    # @wolfmodyt and OWNER_IDS always have super admin permission
    if is_user_allowed_private(user):
        return True
    if chat_id < 0:
        try:
            member = await bot.get_chat_member(chat_id, user.id)
            return member.status in ["administrator", "creator"]
        except Exception:
            return False
    return False
