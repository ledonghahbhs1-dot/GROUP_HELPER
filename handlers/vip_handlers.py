import asyncio
import html
from typing import Dict, Set

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from utils.emoji_helper import emoji_mgr, safe_send_message
from utils.logger import logger
from utils.wolfmod_api import (
    create_vip_invoice,
    check_vip_order,
    create_vietqr_invoice,
    check_vietqr_order,
    get_qr_image_bytes,
)

router = Router(name="vip_handlers")

# Must match the exact "plan" values / VND tiers the wolfmod.xyz backend expects
# (api/index.ts: POST /api/vip/purchase-usdt, POST /api/buy-vip/vietqr-create)
VIP_PLANS: Dict[str, Dict[str, str]] = {
    "2day": {"label": "💎 2 Days - $1 USD", "usd": "1", "vnd": 25000, "duration": "2 Days"},
    "1month": {"label": "👑 30 Days - $7 USD", "usd": "7", "vnd": 150000, "duration": "30 Days"},
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


def build_method_keyboard(plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 💳 Pay with USDT (Crypto)", callback_data=f"vippay:{plan}:usdt")],
        [InlineKeyboardButton(text="👑 🏦 Pay with Bank Transfer (VietQR/SePay)", callback_data=f"vippay:{plan}:vietqr")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="vipbuy:menu")],
    ])


async def send_vip_plan_menu(bot: Bot, chat_id: int):
    """Shows the VIP plan picker. Entry point for the "Buy VIP Key" deep link."""
    text = (
        f"{emoji_mgr.vip} <b>BUY VIP KEY - DRAGON CITY</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} Choose a plan below. Pay with crypto (USDT) or bank transfer (VietQR) - "
        f"your key is delivered <b>automatically</b> right after payment is confirmed.\n\n"
        f"{emoji_mgr.star} <b>💎 2 Days:</b> $1 USD\n"
        f"{emoji_mgr.star} <b>👑 30 Days:</b> $7 USD\n\n"
        f"{emoji_mgr.diamond} <i>Need help?</i> DM {emoji_mgr.vip} :@wolfmodyt"
    )
    await safe_send_message(
        bot, chat_id, emoji_mgr.format_msg(text),
        parse_mode="HTML", reply_markup=build_plan_keyboard()
    )


async def deliver_vip_key(bot: Bot, chat_id: int, dedup_key: str, license_key: str, duration: str):
    """Sends the purchased VIP key to the buyer. Safe to call more than once (deduped)."""
    if dedup_key in _delivered_orders:
        return
    _delivered_orders.add(dedup_key)

    text = (
        f"{emoji_mgr.vip} <b>PAYMENT SUCCESSFUL!</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Plan:</b> VIP {duration}\n"
        f"{emoji_mgr.star} <b>Your VIP Key:</b>\n<code>{html.escape(license_key)}</code>\n\n"
        f"{emoji_mgr.diamond} <b>Activate at:</b> <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n"
        f"{emoji_mgr.star} <i>Need help activating?</i> DM {emoji_mgr.vip} :@wolfmodyt"
    )
    await safe_send_message(bot, chat_id, emoji_mgr.format_msg(text), parse_mode="HTML", disable_web_page_preview=True)
    logger.info("VIP key delivered for order %s to chat %s", dedup_key, chat_id)


async def poll_usdt_order(bot: Bot, chat_id: int, order_id: str, duration: str):
    """Background auto-check for a Plisio/USDT order so most buyers never have to press the manual button."""
    dedup_key = f"usdt:{order_id}"
    for _ in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SEC)
        if dedup_key in _delivered_orders:
            return
        try:
            result = await check_vip_order(order_id)
        except Exception as e:
            logger.error("Poll error for USDT order %s: %s", order_id, e)
            continue

        if result and result.get("status") == "completed" and result.get("licenseKey"):
            await deliver_vip_key(bot, chat_id, dedup_key, result["licenseKey"], duration)
            return

    logger.info("USDT order %s polling timed out after %s attempts (manual check-button still works)", order_id, POLL_MAX_ATTEMPTS)


async def poll_vietqr_order(bot: Bot, chat_id: int, pending_id: str, transfer_code: str, duration: str):
    """Background auto-check for a VietQR/SePay order."""
    dedup_key = f"vietqr:{pending_id}"
    for _ in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SEC)
        if dedup_key in _delivered_orders:
            return
        try:
            result = await check_vietqr_order(pending_id, transfer_code)
        except Exception as e:
            logger.error("Poll error for VietQR order %s: %s", pending_id, e)
            continue

        if result and result.get("status") == "confirmed" and result.get("licenseKey"):
            await deliver_vip_key(bot, chat_id, dedup_key, result["licenseKey"], duration)
            return
        if result and result.get("status") == "expired":
            logger.info("VietQR order %s expired before payment", pending_id)
            return

    logger.info("VietQR order %s polling timed out after %s attempts (manual check-button still works)", pending_id, POLL_MAX_ATTEMPTS)


@router.callback_query(F.data == "vipbuy:menu")
async def on_vip_menu_back(callback: CallbackQuery, bot: Bot):
    if not callback.message:
        await callback.answer()
        return
    await callback.answer()
    await send_vip_plan_menu(bot, callback.message.chat.id)


@router.callback_query(F.data.startswith("vipbuy:"))
async def on_vip_plan_selected(callback: CallbackQuery, bot: Bot):
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Please use this button in a private chat with the bot!", show_alert=True)
        return

    plan = callback.data.split(":", 1)[1]
    plan_info = VIP_PLANS.get(plan)
    if not plan_info:
        await callback.answer("Invalid plan.", show_alert=True)
        return

    await callback.answer()
    text = (
        f"{emoji_mgr.vip} <b>{plan_info['label']}</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} Choose a payment method:"
    )
    await safe_send_message(
        bot, callback.message.chat.id, emoji_mgr.format_msg(text),
        parse_mode="HTML", reply_markup=build_method_keyboard(plan)
    )


@router.callback_query(F.data.startswith("vippay:"))
async def on_vip_method_selected(callback: CallbackQuery, bot: Bot):
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Please use this button in a private chat with the bot!", show_alert=True)
        return

    _, plan, method = callback.data.split(":", 2)
    plan_info = VIP_PLANS.get(plan)
    if not plan_info:
        await callback.answer("Invalid plan.", show_alert=True)
        return

    chat_id = callback.message.chat.id
    user = callback.from_user

    if method == "usdt":
        await callback.answer("⏳ Creating your payment invoice...")
        invoice = await create_vip_invoice(plan)
        if not invoice:
            await safe_send_message(
                bot, chat_id,
                emoji_mgr.format_msg(
                    f"{emoji_mgr.error} <b>Could not create a payment invoice right now.</b>\n"
                    f"Please try again later or contact {emoji_mgr.vip} :@wolfmodyt"
                ),
                parse_mode="HTML"
            )
            return

        order_id = invoice["orderId"]
        invoice_url = invoice["invoiceUrl"]
        qr_bytes = get_qr_image_bytes(invoice.get("qrCode"), invoice_url)

        caption = (
            f"{emoji_mgr.vip} <b>PAY VIP KEY - {plan_info['duration'].upper()} (USDT)</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.star} <b>Amount:</b> <code>${plan_info['usd']} USD</code> (USDT - BEP20 network)\n"
            f"{emoji_mgr.star} <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n\n"
            f"{emoji_mgr.warn} Scan the QR code or tap the button below to pay. Your key is delivered "
            f"<b>automatically</b> right after payment is confirmed (usually within 1-5 minutes).\n\n"
            f"{emoji_mgr.diamond} <i>This invoice expires in 2 hours.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 🔗 Open Payment Page", url=invoice_url)],
            [InlineKeyboardButton(text="👑 🔄 I've Paid - Check Now", callback_data=f"vipcheck:usdt:{order_id}")],
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
            logger.error("Failed to send USDT payment QR for order %s: %s", order_id, e)
            await safe_send_message(
                bot, chat_id,
                emoji_mgr.format_msg(caption) + f"\n\n{emoji_mgr.star} <i>Could not send the QR image, please use the link above.</i>",
                parse_mode="HTML", reply_markup=keyboard
            )

        asyncio.create_task(poll_usdt_order(bot, chat_id, order_id, plan_info["duration"]))

    elif method == "vietqr":
        await callback.answer("⏳ Creating your payment order...")
        username = f"TG-{user.id}" if user else "TG-Unknown"
        invoice = await create_vietqr_invoice(username, plan_info["vnd"])
        if not invoice:
            await safe_send_message(
                bot, chat_id,
                emoji_mgr.format_msg(
                    f"{emoji_mgr.error} <b>Could not create a payment order right now.</b>\n"
                    f"Please try again later or contact {emoji_mgr.vip} :@wolfmodyt"
                ),
                parse_mode="HTML"
            )
            return

        pending_id = str(invoice["pendingId"])
        transfer_code = invoice["transferCode"]
        qr_url = invoice.get("qrUrl")

        caption = (
            f"{emoji_mgr.vip} <b>PAY VIP KEY - {plan_info['duration'].upper()} (BANK TRANSFER)</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.star} <b>Amount:</b> <code>{invoice['amount']:,} VND</code>\n"
            f"{emoji_mgr.star} <b>Bank:</b> {html.escape(invoice.get('bankName', ''))}\n"
            f"{emoji_mgr.star} <b>Account Name:</b> {html.escape(invoice.get('accountName', ''))}\n"
            f"{emoji_mgr.star} <b>Account Number:</b> <code>{html.escape(invoice.get('accountNo', ''))}</code>\n"
            f"{emoji_mgr.star} <b>Transfer Content (required):</b> <code>{html.escape(invoice['memo'])}</code>\n\n"
            f"{emoji_mgr.warn} Scan the QR code with your banking app, or transfer manually using the info above "
            f"(the transfer content <b>must</b> match exactly). Your key is delivered <b>automatically</b> right "
            f"after payment is confirmed (usually within 1-2 minutes).\n\n"
            f"{emoji_mgr.diamond} <i>This order expires in 5 minutes.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 🔄 I've Paid - Check Now", callback_data=f"vipcheck:vietqr:{pending_id}:{transfer_code}")],
        ])

        try:
            if qr_url:
                await bot.send_photo(
                    chat_id=chat_id, photo=qr_url,
                    caption=emoji_mgr.format_msg(caption), parse_mode="HTML", reply_markup=keyboard,
                )
            else:
                await safe_send_message(bot, chat_id, emoji_mgr.format_msg(caption), parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            logger.error("Failed to send VietQR payment QR for order %s: %s", pending_id, e)
            await safe_send_message(bot, chat_id, emoji_mgr.format_msg(caption), parse_mode="HTML", reply_markup=keyboard)

        asyncio.create_task(poll_vietqr_order(bot, chat_id, pending_id, transfer_code, plan_info["duration"]))


@router.callback_query(F.data.startswith("vipcheck:"))
async def on_vip_check(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":", 2)
    method = parts[1]
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id

    if method == "usdt":
        order_id = parts[2]
        dedup_key = f"usdt:{order_id}"
        if dedup_key in _delivered_orders:
            await callback.answer("✅ Key already delivered, please check the message above!", show_alert=True)
            return

        await callback.answer("🔍 Checking payment...")
        result = await check_vip_order(order_id)
        if not result:
            await callback.answer("❌ Could not check status right now, please try again later.", show_alert=True)
            return

        if result.get("status") == "completed" and result.get("licenseKey"):
            await deliver_vip_key(bot, chat_id, dedup_key, result["licenseKey"], "VIP")
        else:
            await callback.answer("⏳ Payment not received yet. Please wait a few minutes after paying and try again.", show_alert=True)

    elif method == "vietqr":
        pending_id, transfer_code = parts[2].split(":", 1)
        dedup_key = f"vietqr:{pending_id}"
        if dedup_key in _delivered_orders:
            await callback.answer("✅ Key already delivered, please check the message above!", show_alert=True)
            return

        await callback.answer("🔍 Checking payment...")
        result = await check_vietqr_order(pending_id, transfer_code)
        if not result:
            await callback.answer("❌ Could not check status right now, please try again later.", show_alert=True)
            return

        status = result.get("status")
        if status == "confirmed" and result.get("licenseKey"):
            await deliver_vip_key(bot, chat_id, dedup_key, result["licenseKey"], "VIP")
        elif status == "expired":
            await callback.answer("⌛ This order has expired. Please create a new one with /start buyvip.", show_alert=True)
        else:
            await callback.answer("⏳ Payment not received yet. Please wait a few minutes after transferring and try again.", show_alert=True)
