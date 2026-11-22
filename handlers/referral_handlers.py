"""Referral invite links + manually posted group events (task 102).

Nothing in here grants a reward: milestones only produce a congratulation in the group and a private note for the admin(s)
(config.REFERRAL_ADMIN_IDS) who decide the reward by hand.
"""
import asyncio
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, LEFT, KICKED
from aiogram.types import ChatMemberUpdated, Message

import config
from database.db import db
from database.referral import ReferralStore, referral_store
from utils.auth import is_admin_or_owner
from utils.logger import logger

router = Router(name="referral_handlers")

GROUP_TYPES = ("group", "supergroup")
ANONYMOUS_ADMIN_BOT_ID = 1087968824
REF_NAME_RE = re.compile(r"^ref:(\d{1,15})$")
MAX_EVENT_TEXT = 3500
MAX_EVENT_SECONDS = 30 * 24 * 3600
VN_TZ = timezone(timedelta(hours=7))
LOOP_INTERVAL_SEC = 60
STALE_PENDING_SEC = 24 * 3600  # a pending join we can never resolve (bot lost access) is dropped after a day


def confirm_window_sec() -> int:
    return int(config.REFERRAL_CONFIRM_MINUTES) * 60


# ---------------------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------------------
def referrer_from_invite_link(invite_link, bot_id: int) -> Optional[int]:
    """Referrer id for a link that WE created. The name must be `ref:<id>` and the creator must be this bot: any chat admin
    can create a link with an arbitrary name, so the name alone is never trusted."""
    if invite_link is None:
        return None
    match = REF_NAME_RE.match(str(getattr(invite_link, "name", "") or ""))
    creator = getattr(invite_link, "creator", None)
    if not match or creator is None or getattr(creator, "id", None) != bot_id:
        return None
    referrer_id = int(match.group(1))
    return referrer_id if referrer_id > 0 else None


def mention(user_id: int, name: str = "") -> str:
    return f'<a href="tg://user?id={int(user_id)}">{html.escape(name or "bạn")}</a>'


async def _display_name(user_id: int) -> str:
    try:
        row = await db.get_user_by_id(user_id)
        if row:
            return row.get("full_name") or row.get("username") or ""
    except Exception:
        pass
    return ""


def parse_event_args(raw: str) -> Tuple[Optional[int], bool, str]:
    """`[2h|30m|1d] [nopin] <text>` -> (duration_seconds | None, pin, text). Raises ValueError with a user-facing reason."""
    duration: Optional[int] = None
    pin = True
    rest = (raw or "").strip()
    for _ in range(2):  # at most one duration and one "nopin", in any order, before the text
        match = re.match(r"(\S+)(?:\s+|$)", rest)
        if not match:
            break
        token = match.group(1).lower()
        unit = re.fullmatch(r"(\d{1,5})([mhd])", token)
        if unit and duration is None:
            duration = int(unit.group(1)) * {"m": 60, "h": 3600, "d": 86400}[unit.group(2)]
            if duration <= 0 or duration > MAX_EVENT_SECONDS:
                raise ValueError("Thời gian phải từ 1 phút đến 30 ngày.")
        elif token == "nopin" and pin:
            pin = False
        else:
            break
        rest = rest[match.end():]
    text = rest.strip()  # keeps the admin's own line breaks
    if not text:
        raise ValueError("Thiếu nội dung sự kiện.")
    if len(text) > MAX_EVENT_TEXT:
        raise ValueError(f"Nội dung quá dài (tối đa {MAX_EVENT_TEXT} ký tự).")
    return duration, pin, text


def format_end(ends_at: Optional[int]) -> str:
    return datetime.fromtimestamp(ends_at, VN_TZ).strftime("%H:%M %d/%m/%Y") if ends_at else ""


async def _is_admin(message: Message, bot: Bot) -> bool:
    return await is_admin_or_owner(message.chat.id, message.from_user, bot, getattr(message, "sender_chat", None))


# ---------------------------------------------------------------------------------------------------------------------
# referral links
# ---------------------------------------------------------------------------------------------------------------------
async def get_or_create_link(bot: Bot, chat_id: int, user_id: int, store: Optional[ReferralStore] = None) -> Optional[str]:
    """The user's own invite link for this chat (one per user, reused). None when the bot may not create links."""
    store = store or referral_store
    existing = await store.get_link(chat_id, user_id)
    if existing:
        return existing["invite_link"]
    name = f"ref:{user_id}"
    try:
        created = await bot.create_chat_invite_link(chat_id=chat_id, name=name)
    except TelegramAPIError as error:
        logger.warning("create_chat_invite_link failed in %s: %s", chat_id, error)
        return None
    await store.save_link(chat_id, user_id, created.invite_link, name)
    return created.invite_link


@router.message(Command("moi", "invite"))
async def cmd_invite(message: Message, bot: Bot):
    user = message.from_user
    if message.chat.type not in GROUP_TYPES:
        await message.reply("Hãy dùng lệnh /moi trong nhóm để nhận link mời riêng của bạn.")
        return
    if user is None or user.is_bot or user.id == ANONYMOUS_ADMIN_BOT_ID:
        await message.reply("Không tạo được link mời cho tài khoản ẩn danh. Hãy tắt chế độ ẩn danh rồi thử lại.")
        return
    link = await get_or_create_link(bot, message.chat.id, user.id)
    if not link:
        await message.reply("Bot chưa có quyền tạo link mời (cần quyền \"Mời người dùng qua liên kết\"). Hãy báo admin.")
        return
    minutes = int(config.REFERRAL_CONFIRM_MINUTES)
    await message.reply(
        f"🔗 <b>Link mời riêng của bạn:</b>\n{html.escape(link)}\n\n"
        f"Mỗi người vào nhóm bằng link này và ở lại ít nhất {minutes} phút sẽ được tính cho bạn. "
        f"Xem tiến độ bằng /moi_cua_toi.", parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("moi_cua_toi", "my_referrals"))
async def cmd_my_referrals(message: Message, bot: Bot):
    user = message.from_user
    if message.chat.type not in GROUP_TYPES or user is None:
        await message.reply("Hãy dùng lệnh /moi_cua_toi trong nhóm.")
        return
    counts = await referral_store.get_counts(message.chat.id, user.id)
    confirmed = counts["confirmed"]
    upcoming = [m for m in config.REFERRAL_MILESTONES if m > confirmed]
    lines = [f"📊 <b>Lượt mời của bạn:</b> {confirmed} thành công"]
    if counts["pending"]:
        lines.append(f"⏳ Đang chờ xác nhận: {counts['pending']} (cần ở lại {int(config.REFERRAL_CONFIRM_MINUTES)} phút)")
    if upcoming:
        lines.append(f"🎯 Mốc tiếp theo: {upcoming[0]} người (còn thiếu {upcoming[0] - confirmed})")
    else:
        lines.append("🏆 Bạn đã đạt tất cả các mốc hiện có. Cảm ơn bạn!")
    lines.append("Dùng /moi để lấy link mời riêng. Phần thưởng do admin xét thủ công.")
    await message.reply("\n".join(lines), parse_mode="HTML")


async def on_member_joined(bot: Bot, event: ChatMemberUpdated, store: Optional[ReferralStore] = None) -> bool:
    """Called by member_handlers when a member joins. Records a PENDING referral if the invite link is one of ours."""
    store = store or referral_store
    new_user = event.new_chat_member.user
    if event.chat.type not in GROUP_TYPES or new_user is None or new_user.is_bot:
        return False
    referrer_id = referrer_from_invite_link(getattr(event, "invite_link", None), bot.id)
    if referrer_id is None:
        return False
    recorded = await store.record_join(event.chat.id, new_user.id, referrer_id)
    if recorded:
        logger.info("Referral pending: member %s joined %s via link of %s", new_user.id, event.chat.id, referrer_id)
    return recorded


async def _announce_milestone(bot: Bot, chat_id: int, referrer_id: int, milestone: int, count: int):
    name = await _display_name(referrer_id)
    tag = mention(referrer_id, name)
    try:
        await bot.send_message(
            chat_id, f"🎉 Chúc mừng {tag} đã mời thành công <b>{milestone}</b> thành viên vào nhóm! "
                     f"Admin sẽ xét phần thưởng.", parse_mode="HTML")
    except TelegramAPIError as error:
        logger.warning("Milestone group message failed in %s: %s", chat_id, error)
    for admin_id in config.REFERRAL_ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, f"🏅 Mốc mời {milestone} người: {tag} (ID {referrer_id}) trong nhóm {chat_id}, hiện có {count} lượt "
                          f"thành công. Hãy tự xét thưởng (bot KHÔNG tự cấp key/quà).", parse_mode="HTML")
        except TelegramAPIError as error:
            logger.warning("Milestone admin note to %s failed: %s", admin_id, error)


async def confirm_and_announce(bot: Bot, chat_id: int, member_id: int, store: Optional[ReferralStore] = None) -> Optional[int]:
    """pending -> confirmed (+1), then announce every newly reached milestone exactly once. Returns the new count."""
    store = store or referral_store
    join = await store.get_join(chat_id, member_id)
    count = await store.confirm_join(chat_id, member_id)
    if count is None or join is None:
        return None
    reached = [m for m in config.REFERRAL_MILESTONES if m <= count and await store.claim_milestone(chat_id, join["referrer_id"], m)]
    if reached:
        await _announce_milestone(bot, chat_id, join["referrer_id"], max(reached), count)
    return count


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=LEFT | KICKED))
async def on_member_gone(event: ChatMemberUpdated, bot: Bot):
    await handle_member_gone(bot, event)


async def handle_member_gone(bot: Bot, event: ChatMemberUpdated, store: Optional[ReferralStore] = None) -> str:
    """Left/kicked/banned. Before the confirm window the invite never counts; after it, it already did."""
    store = store or referral_store
    chat_id, member_id = event.chat.id, event.new_chat_member.user.id
    join = await store.get_join(chat_id, member_id)
    if not join or join["status"] != "pending":
        return "ignored"
    if store.now() - join["joined_at"] >= confirm_window_sec():
        await confirm_and_announce(bot, chat_id, member_id, store)
        return "confirmed"
    await store.revoke_join(chat_id, member_id)
    return "revoked"


async def process_due_referrals(bot: Bot, store: Optional[ReferralStore] = None) -> dict:
    """Resolves pending joins older than the confirm window by checking who is really still in the chat."""
    store = store or referral_store
    summary = {"confirmed": 0, "revoked": 0, "retry": 0}
    for join in await store.due_pending(confirm_window_sec()):
        chat_id, member_id = join["chat_id"], join["member_id"]
        try:
            member = await bot.get_chat_member(chat_id, member_id)
        except TelegramAPIError as error:
            if store.now() - join["joined_at"] > STALE_PENDING_SEC:
                await store.revoke_join(chat_id, member_id)
                summary["revoked"] += 1
            else:
                logger.warning("Referral check failed for %s in %s: %s", member_id, chat_id, error)
                summary["retry"] += 1
            continue
        still_in = member.status in ("member", "administrator", "creator") or (
            member.status == "restricted" and getattr(member, "is_member", True))
        if still_in:
            await confirm_and_announce(bot, chat_id, member_id, store)
            summary["confirmed"] += 1
        else:
            await store.revoke_join(chat_id, member_id)
            summary["revoked"] += 1
    return summary


# ---------------------------------------------------------------------------------------------------------------------
# manual group events
# ---------------------------------------------------------------------------------------------------------------------
def event_text(text: str, ends_at: Optional[int]) -> str:
    body = f"📣 <b>SỰ KIỆN</b>\n\n{html.escape(text)}"
    if ends_at:
        body += f"\n\n⏳ <i>Kết thúc: {format_end(ends_at)}</i>"
    return body


@router.message(Command("su_kien", "event"))
async def cmd_event(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type not in GROUP_TYPES:
        await message.reply("Hãy dùng lệnh /su_kien trong nhóm.")
        return
    if not await _is_admin(message, bot):
        await message.reply("⛔ Chỉ admin mới dùng được lệnh này.")
        return
    try:
        duration, pin, text = parse_event_args(command.args or "")
    except ValueError as error:
        await message.reply(f"{error}\nCú pháp: /su_kien [2h|30m|1d] [nopin] <nội dung>")
        return
    ends_at = referral_store.now() + duration if duration else None
    posted = await bot.send_message(message.chat.id, event_text(text, ends_at), parse_mode="HTML")
    pinned = False
    if pin:
        try:
            await bot.pin_chat_message(message.chat.id, posted.message_id, disable_notification=False)
            pinned = True
        except TelegramAPIError as error:
            logger.warning("Could not pin event message in %s: %s", message.chat.id, error)
    user_id = message.from_user.id if message.from_user else 0
    event_id = await referral_store.add_event(message.chat.id, text, user_id, posted.message_id, pinned, ends_at)
    note = "" if pinned or not pin else " (bot chưa ghim được: cần quyền ghim tin nhắn)"
    await message.reply(f"✅ Đã đăng sự kiện #{event_id}{note}. Hủy bằng /huy_su_kien {event_id}.")


@router.message(Command("su_kien_list", "events"))
async def cmd_event_list(message: Message):
    if message.chat.type not in GROUP_TYPES:
        await message.reply("Hãy dùng lệnh /su_kien_list trong nhóm.")
        return
    events = await referral_store.active_events(message.chat.id)
    if not events:
        await message.reply("Hiện không có sự kiện nào đang diễn ra.")
        return
    lines = ["📣 <b>Sự kiện đang diễn ra:</b>"]
    for event in events:
        snippet = html.escape(event["text"][:80] + ("…" if len(event["text"]) > 80 else ""))
        end = f" (đến {format_end(event['ends_at'])})" if event["ends_at"] else ""
        lines.append(f"#{event['id']}: {snippet}{end}")
    await message.reply("\n".join(lines), parse_mode="HTML")


async def _unpin(bot: Bot, event: dict):
    if event.get("pinned") and event.get("message_id"):
        try:
            await bot.unpin_chat_message(event["chat_id"], event["message_id"])
        except TelegramAPIError as error:
            logger.warning("Could not unpin event %s: %s", event["id"], error)


@router.message(Command("huy_su_kien", "cancel_event"))
async def cmd_cancel_event(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type not in GROUP_TYPES:
        await message.reply("Hãy dùng lệnh /huy_su_kien trong nhóm.")
        return
    if not await _is_admin(message, bot):
        await message.reply("⛔ Chỉ admin mới dùng được lệnh này.")
        return
    arg = (command.args or "").strip()
    active = await referral_store.active_events(message.chat.id)
    if arg:
        if not arg.isdigit():
            await message.reply("Cú pháp: /huy_su_kien <số thứ tự sự kiện>")
            return
        event = await referral_store.get_event(message.chat.id, int(arg))
    elif len(active) == 1:
        event = active[0]
    else:
        await message.reply("Có nhiều sự kiện đang chạy, hãy ghi rõ số: /huy_su_kien <số> (xem /su_kien_list).")
        return
    if not event or event["status"] != "active" or not await referral_store.finish_event(event["id"], "cancelled"):
        await message.reply("Không tìm thấy sự kiện đang diễn ra với số đó.")
        return
    await _unpin(bot, event)
    await message.reply(f"✅ Đã hủy sự kiện #{event['id']}.")


async def expire_events(bot: Bot, store: Optional[ReferralStore] = None) -> int:
    """Ends events whose time is up: unpins and posts a short notice. Returns how many ended."""
    store = store or referral_store
    ended = 0
    for event in await store.expired_events():
        if not await store.finish_event(event["id"], "ended"):
            continue
        await _unpin(bot, event)
        try:
            await bot.send_message(event["chat_id"], f"⏹ Sự kiện #{event['id']} đã kết thúc. Cảm ơn mọi người đã tham gia!")
        except TelegramAPIError as error:
            logger.warning("Event end notice failed for %s: %s", event["id"], error)
        ended += 1
    return ended


async def referral_loop(bot: Bot):
    """Background task: resolves pending referrals and ends timed events. Runs for the life of the process."""
    while True:
        try:
            await process_due_referrals(bot)
            await expire_events(bot)
        except Exception as error:  # never let the loop die
            logger.error("referral_loop error: %s", error)
        await asyncio.sleep(LOOP_INTERVAL_SEC)
