from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db
from utils.emoji_helper import emoji_mgr
from utils.auth import is_admin_or_owner
from utils.logger import logger
import config

router = Router(name="callback_handlers")

def build_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    spam_status = "ON ✅" if settings.get("anti_spam", 1) else "OFF ❌"
    link_status = "ON ✅" if settings.get("anti_link", 1) else "OFF ❌"
    bot_status = "ON ✅" if settings.get("anti_bot", 1) else "OFF ❌"
    badwords_status = "ON ✅" if settings.get("anti_badwords", 1) else "OFF ❌"
    auto_del_status = "ON (30s) ✅" if settings.get("auto_delete_logs", 1) else "OFF ❌"
    max_warns = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
    warn_action = settings.get("warn_action", config.DEFAULT_WARN_ACTION).upper()

    return InlineKeyboardMarkup(inline_keyboard=[
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

@router.callback_query()
async def on_settings_callback(callback: CallbackQuery, bot: Bot):
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    chat_id = callback.message.chat.id

    if not await is_admin_or_owner(chat_id, callback.from_user, bot):
        await callback.answer("❌ You are not an Administrator of this group!", show_alert=True)
        return

    data = callback.data
    settings = await db.get_chat_settings(chat_id)

    if data.startswith("quick_unban:"):
        u_id_str = data.split(":", 1)[1]
        if u_id_str.isdigit():
            target_user_id = int(u_id_str)
            try:
                await bot.unban_chat_member(chat_id, target_user_id)
                await db.reset_warns(chat_id, target_user_id)
                await db.remove_banned_user(chat_id, target_user_id)
                await callback.answer(f"✅ Đã gỡ cấm (unbanned) thành viên {target_user_id} thành công!", show_alert=True)
                # Refresh banned list message
                banned_list = await db.get_banned_users(chat_id, limit=30)
                if not banned_list:
                    text = f"{emoji_mgr.shield} <b>DANH SÁCH BAN / BANNED LIST</b> {emoji_mgr.vip}\n\nHiện tại nhóm không có thành viên nào trong danh sách bị cấm!"
                    await callback.message.edit_text(emoji_mgr.format_msg(text), parse_mode="HTML")
                else:
                    lines = [f"{emoji_mgr.ban} <b>DANH SÁCH THÀNH VIÊN ĐÃ BỊ CẤM ({len(banned_list)})</b> {emoji_mgr.vip}\n"]
                    buttons = []
                    for idx, u in enumerate(banned_list, 1):
                        u_id = u["user_id"]
                        u_name = u["full_name"] or f"User {u_id}"
                        u_uname = f"(@{u['username']})" if u.get("username") else ""
                        reason = u.get("reason") or "Rule violation"
                        lines.append(f"<b>{idx}.</b> {u_name} {u_uname}\n└ <code>{u_id}</code> | Lý do: <i>{reason}</i>")
                        btn_label = f"🔓 Gỡ {u['username'] or u_id}"[:30]
                        buttons.append([InlineKeyboardButton(text=btn_label, callback_data=f"quick_unban:{u_id}")])
                    lines.append(f"\n💡 <i>Bấm nút bên dưới để gỡ cấm hoặc gõ:</i> <code>/unban &lt;ID hoặc @username&gt;</code>")
                    await callback.message.edit_text(emoji_mgr.format_msg("\n".join(lines)), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Lỗi khi gỡ cấm: {e}", show_alert=True)
        return

    if data == "close_settings":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("Settings closed.")
        return

    if data == "toggle_anti_spam":
        new_val = 0 if settings.get("anti_spam", 1) else 1
        await db.update_chat_setting(chat_id, "anti_spam", new_val)
        status_txt = "ON" if new_val else "OFF"
        await callback.answer(f"Anti-Spam: {status_txt}")

    elif data == "toggle_anti_link":
        new_val = 0 if settings.get("anti_link", 1) else 1
        await db.update_chat_setting(chat_id, "anti_link", new_val)
        status_txt = "ON" if new_val else "OFF"
        await callback.answer(f"Anti-Link: {status_txt}")

    elif data == "toggle_anti_bot":
        new_val = 0 if settings.get("anti_bot", 1) else 1
        await db.update_chat_setting(chat_id, "anti_bot", new_val)
        status_txt = "ON" if new_val else "OFF"
        await callback.answer(f"Anti-Bot: {status_txt}")

    elif data == "toggle_anti_badwords":
        new_val = 0 if settings.get("anti_badwords", 1) else 1
        await db.update_chat_setting(chat_id, "anti_badwords", new_val)
        status_txt = "ON" if new_val else "OFF"
        await callback.answer(f"Anti-Profanity: {status_txt}")

    elif data == "toggle_auto_del":
        new_val = 0 if settings.get("auto_delete_logs", 1) else 1
        await db.update_chat_setting(chat_id, "auto_delete_logs", new_val)
        status_txt = "ON" if new_val else "OFF"
        await callback.answer(f"Auto-delete 30s: {status_txt}")

    elif data == "cycle_max_warns":
        current = settings.get("max_warns", config.DEFAULT_MAX_WARNS)
        warn_steps = [1, 2, 3, 5, 10]
        try:
            idx = (warn_steps.index(current) + 1) % len(warn_steps)
            new_val = warn_steps[idx]
        except ValueError:
            new_val = 5
        await db.update_chat_setting(chat_id, "max_warns", new_val)
        await callback.answer(f"Max warnings set to {new_val}")

    elif data == "cycle_warn_action":
        current = settings.get("warn_action", config.DEFAULT_WARN_ACTION).lower()
        actions = ["ban", "mute", "kick"]
        try:
            idx = (actions.index(current) + 1) % len(actions)
            new_val = actions[idx]
        except ValueError:
            new_val = "ban"
        await db.update_chat_setting(chat_id, "warn_action", new_val)
        await callback.answer(f"Punishment on max warns: {new_val.upper()}")

    # Refresh keyboard
    updated_settings = await db.get_chat_settings(chat_id)
    new_keyboard = build_settings_keyboard(updated_settings)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception:
        pass
