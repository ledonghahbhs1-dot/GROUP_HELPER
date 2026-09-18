import asyncio
import html
from typing import Dict, Set

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from utils.emoji_helper import emoji_mgr, safe_send_message
from utils.logger import logger
from utils.wolfmod_api import create_vip_invoice, check_vip_order, get_qr_image_bytes

router = Router(name="vip_handlers")

# Must match the exact "plan" values the wolfmod.xyz backend expects
# (api/index.ts: POST /api/vip/purchase-usdt)
VIP_PLANS: Dict[str, Dict[str, str]] = {
    "2day": {"label": "💎 2 Ngày - $1 USD", "usd": "1", "duration_vi": "2 Ngày"},
    "1month": {"label": "👑 30 Ngày - $7 USD", "usd": "7", "duration_vi": "30 Ngày"},
}

# In-memory guard against delivering the same key twice (background poll + manual check race)
_delivered_orders: Set[str] = set()

# Background poll: check every 10s for up to 30 minutes before giving up (manual "Check" button still works after)
POLL_INTERVAL_SEC = 10
POLL_MAX_ATTEMPTS = 180


def build_plan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=VIP_PLANS["2day"]["label"], callback_data="vipbuy:2day")],
        [InlineKeyboardButton(text=VIP_PLANS["1month"]["label"], callback_data="vipbuy:1month")],
    ])


async def send_vip_plan_menu(bot: Bot, chat_id: int):
    """Shows the VIP plan picker. Entry point for the "Buy VIP Key" deep link."""
    text = (
        f"{emoji_mgr.vip} <b>MUA VIP KEY - DRAGON CITY</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} Chọn gói bạn muốn mua bên dưới. Thanh toán bằng USDT (mạng BEP20), "
        f"Key sẽ được gửi <b>tự động</b> ngay sau khi thanh toán được xác nhận.\n\n"
        f"{emoji_mgr.star} <b>💎 2 Ngày:</b> $1 USD\n"
        f"{emoji_mgr.star} <b>👑 30 Ngày:</b> $7 USD\n\n"
        f"{emoji_mgr.diamond} <i>Cần hỗ trợ? DM</i> {emoji_mgr.vip} :@wolfmodyt"
    )
    await safe_send_message(
        bot, chat_id, emoji_mgr.format_msg(text),
        parse_mode="HTML", reply_markup=build_plan_keyboard()
    )


async def deliver_vip_key(bot: Bot, chat_id: int, order_id: str, license_key: str, duration_vi: str):
    """Sends the purchased VIP key to the buyer. Safe to call more than once (deduped)."""
    if order_id in _delivered_orders:
        return
    _delivered_orders.add(order_id)

    text = (
        f"{emoji_mgr.vip} <b>THANH TOÁN THÀNH CÔNG!</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Gói:</b> VIP {duration_vi}\n"
        f"{emoji_mgr.star} <b>VIP Key của bạn:</b>\n<code>{html.escape(license_key)}</code>\n\n"
        f"{emoji_mgr.diamond} <b>Kích hoạt tại:</b> <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n"
        f"{emoji_mgr.star} <i>Cần hỗ trợ kích hoạt?</i> DM {emoji_mgr.vip} :@wolfmodyt"
    )
    await safe_send_message(bot, chat_id, emoji_mgr.format_msg(text), parse_mode="HTML", disable_web_page_preview=True)
    logger.info("VIP key delivered for order %s to chat %s", order_id, chat_id)


async def poll_vip_order(bot: Bot, chat_id: int, order_id: str, duration_vi: str):
    """Background auto-check so most buyers never have to press the manual button."""
    for _ in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SEC)
        if order_id in _delivered_orders:
            return
        try:
            result = await check_vip_order(order_id)
        except Exception as e:
            logger.error("Poll error for VIP order %s: %s", order_id, e)
            continue

        if result and result.get("status") == "completed" and result.get("licenseKey"):
            await deliver_vip_key(bot, chat_id, order_id, result["licenseKey"], duration_vi)
            return

    logger.info("VIP order %s polling timed out after %s attempts (manual check-button still works)", order_id, POLL_MAX_ATTEMPTS)


@router.callback_query(F.data.startswith("vipbuy:"))
async def on_vip_plan_selected(callback: CallbackQuery, bot: Bot):
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Vui lòng bấm nút này trong tin nhắn riêng với bot!", show_alert=True)
        return

    plan = callback.data.split(":", 1)[1]
    plan_info = VIP_PLANS.get(plan)
    if not plan_info:
        await callback.answer("Gói không hợp lệ.", show_alert=True)
        return

    await callback.answer("⏳ Đang tạo hoá đơn thanh toán...")
    chat_id = callback.message.chat.id

    invoice = await create_vip_invoice(plan)
    if not invoice:
        await safe_send_message(
            bot, chat_id,
            emoji_mgr.format_msg(
                f"{emoji_mgr.error} <b>Không thể tạo hoá đơn thanh toán lúc này.</b>\n"
                f"Vui lòng thử lại sau hoặc liên hệ {emoji_mgr.vip} :@wolfmodyt"
            ),
            parse_mode="HTML"
        )
        return

    order_id = invoice["orderId"]
    invoice_url = invoice["invoiceUrl"]
    qr_bytes = get_qr_image_bytes(invoice.get("qrCode"), invoice_url)

    caption = (
        f"{emoji_mgr.vip} <b>THANH TOÁN VIP KEY - {plan_info['duration_vi'].upper()}</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Số tiền:</b> <code>${plan_info['usd']} USD</code> (USDT - mạng BEP20)\n"
        f"{emoji_mgr.star} <b>Mã đơn hàng:</b> <code>{html.escape(order_id)}</code>\n\n"
        f"{emoji_mgr.warn} Quét mã QR hoặc bấm nút bên dưới để thanh toán. Key sẽ được gửi <b>tự động</b> "
        f"ngay sau khi thanh toán được xác nhận (thường trong 1-5 phút).\n\n"
        f"{emoji_mgr.diamond} <i>Hoá đơn hết hạn sau 2 giờ.</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Mở trang thanh toán", url=invoice_url)],
        [InlineKeyboardButton(text="🔄 Tôi đã thanh toán - Kiểm tra ngay", callback_data=f"vipcheck:{order_id}")],
    ])

    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=BufferedInputFile(qr_bytes.read(), filename="vip_payment_qr.png"),
            caption=emoji_mgr.format_msg(caption),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error("Failed to send VIP payment QR for order %s: %s", order_id, e)
        await safe_send_message(
            bot, chat_id,
            emoji_mgr.format_msg(caption) + f"\n\n{emoji_mgr.star} <i>Không thể gửi ảnh QR, hãy dùng link phía trên.</i>",
            parse_mode="HTML", reply_markup=keyboard
        )

    asyncio.create_task(poll_vip_order(bot, chat_id, order_id, plan_info["duration_vi"]))


@router.callback_query(F.data.startswith("vipcheck:"))
async def on_vip_check(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split(":", 1)[1]
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id

    if order_id in _delivered_orders:
        await callback.answer("✅ Key đã được gửi trước đó, vui lòng kiểm tra tin nhắn phía trên!", show_alert=True)
        return

    await callback.answer("🔍 Đang kiểm tra thanh toán...")
    result = await check_vip_order(order_id)

    if not result:
        await callback.answer("❌ Không thể kiểm tra trạng thái lúc này, vui lòng thử lại sau.", show_alert=True)
        return

    if result.get("status") == "completed" and result.get("licenseKey"):
        await deliver_vip_key(bot, chat_id, order_id, result["licenseKey"], "VIP")
    else:
        await callback.answer("⏳ Chưa nhận được thanh toán. Vui lòng đợi vài phút sau khi chuyển và thử lại.", show_alert=True)
