from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db
from utils.emoji_helper import emoji_mgr
from utils.logger import logger
from handlers.member_handlers import is_user_admin
import config

router = Router(name="callback_handlers")

def build_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    spam_status = "BẬT ✅" if settings.get("anti_spam", 1) else "TẮT ❌"
    link_status = "BẬT ✅" if settings.get("anti_link", 1) else "TẮT ❌"
    bot_status = "BẬT ✅" if settings.get("anti_bot", 1) else "TẮT ❌"
    badwords_status = "BẬT ✅" if settings.get("anti_badwords", 1) else "TẮT ❌"
    auto_del_status = "BẬT (30s) ✅" if settings.get("auto_delete_logs", 1) else "TẮT ❌"
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION).upper()

    return InlineKeyboardMarkup(inline_keyboard=[
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

@router.callback_query()
async def on_settings_callback(callback: CallbackQuery, bot: Bot):
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    if not await is_user_admin(chat_id, user_id, bot):
        await callback.answer("❌ Bạn không phải là Quản trị viên của nhóm!", show_alert=True)
        return

    data = callback.data
    settings = await db.get_chat_settings(chat_id)

    if data == "close_settings":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("Đã đóng cài đặt.")
        return

    if data == "toggle_anti_spam":
        new_val = 0 if settings.get("anti_spam", 1) else 1
        await db.update_chat_setting(chat_id, "anti_spam", new_val)
        status_txt = "BẬT" if new_val else "TẮT"
        await callback.answer(f"Anti-Spam: {status_txt}")

    elif data == "toggle_anti_link":
        new_val = 0 if settings.get("anti_link", 1) else 1
        await db.update_chat_setting(chat_id, "anti_link", new_val)
        status_txt = "BẬT" if new_val else "TẮT"
        await callback.answer(f"Anti-Link: {status_txt}")

    elif data == "toggle_anti_bot":
        new_val = 0 if settings.get("anti_bot", 1) else 1
        await db.update_chat_setting(chat_id, "anti_bot", new_val)
        status_txt = "BẬT" if new_val else "TẮT"
        await callback.answer(f"Anti-Bot: {status_txt}")

    elif data == "toggle_anti_badwords":
        new_val = 0 if settings.get("anti_badwords", 1) else 1
        await db.update_chat_setting(chat_id, "anti_badwords", new_val)
        status_txt = "BẬT" if new_val else "TẮT"
        await callback.answer(f"Anti-Ngôn từ lăng mạ: {status_txt}")

    elif data == "toggle_auto_del":
        new_val = 0 if settings.get("auto_delete_logs", 1) else 1
        await db.update_chat_setting(chat_id, "auto_delete_logs", new_val)
        status_txt = "BẬT" if new_val else "TẮT"
        await callback.answer(f"Tự xoá tin cảnh báo: {status_txt}")

    elif data == "cycle_max_warns":
        current = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
        # Cycle: 1 -> 2 -> 3 -> 5 -> 1
        warn_steps = [1, 2, 3, 5]
        try:
            idx = (warn_steps.index(current) + 1) % len(warn_steps)
            new_val = warn_steps[idx]
        except ValueError:
            new_val = 2
        await db.update_chat_setting(chat_id, "max_warns", new_val)
        await callback.answer(f"Giới hạn cảnh cáo đặt thành {new_val}")

    elif data == "cycle_warn_action":
        current = settings.get("warn_action", config.DEFAULT_WARN_ACTION).lower()
        # Cycle: ban -> mute -> kick -> ban
        actions = ["ban", "mute", "kick"]
        try:
            idx = (actions.index(current) + 1) % len(actions)
            new_val = actions[idx]
        except ValueError:
            new_val = "ban"
        await db.update_chat_setting(chat_id, "warn_action", new_val)
        await callback.answer(f"Hình phạt khi đủ cảnh cáo: {new_val.upper()}")

    # Refresh keyboard
    updated_settings = await db.get_chat_settings(chat_id)
    new_keyboard = build_settings_keyboard(updated_settings)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception:
        pass
