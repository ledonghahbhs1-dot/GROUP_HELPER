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

async def is_admin_or_owner(chat_id: int, user, bot: Bot, sender_chat=None) -> bool:
    """
    Checks if a user or sender is:
    1. Anonymous Admin / Sending as Group / Sending as Channel (`sender_chat`)
    2. Telegram GroupAnonymousBot (ID: 1087968824)
    3. Super Admin @wolfmodyt or OWNER_IDS
    4. Group Administrator or Creator
    """
    # 1. When sending as Group or Channel (Telegram Anonymous Admin)
    if sender_chat is not None:
        return True

    if not user:
        return False

    # 2. Telegram Official Anonymous Bot & Service Notifications
    if user.id in [1087968824, 777000] or getattr(user, "username", "") == "GroupAnonymousBot":
        return True

    # 3. @wolfmodyt and OWNER_IDS always have super admin permission everywhere
    if is_user_allowed_private(user):
        return True

    # 4. Telegram Group Admin / Creator status check
    if chat_id < 0:
        try:
            member = await bot.get_chat_member(chat_id, user.id)
            return member.status in ["administrator", "creator"]
        except Exception:
            return False

    return False
