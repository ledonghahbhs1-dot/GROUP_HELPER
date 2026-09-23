import asyncio
import html
import re
import time
from typing import Any, Dict, Optional, Set

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, Message

import config
from database.db import db
from utils.emoji_helper import emoji_mgr, safe_send_message
from utils.logger import logger
from utils.wolfmod_api import (
    create_vip_invoice,
    check_vip_order,
    create_vietqr_invoice,
    check_vietqr_order,
    get_qr_image_bytes,
    shorten_link4m,
    generate_free_key,
    get_flash_sale_status,
)

router = Router(name="vip_handlers")

# Must match the exact "plan" values / VND tiers the wolfmod.xyz backend expects
# (api/index.ts: POST /api/vip/purchase-usdt, POST /api/buy-vip/vietqr-create)
VIP_PLANS: Dict[str, Dict[str, str]] = {
    "2day": {"label": "💎 2 Days - $1 USD", "usd": "1", "vnd": 25000, "duration": "2 Days"},
    "1month": {"label": "30 Days - $7 USD", "usd": "7", "vnd": 150000, "duration": "30 Days"},
}

# In-memory guard against delivering the same key twice (background poll + manual check race)
_delivered_orders: Set[str] = set()

_PAID_STATUSES = {"confirmed", "completed", "paid", "success", "successful"}


def _extract_license_key(result: Dict[str, Any]) -> str:
    """Backend variants may name the delivered key differently."""
    return str(
        result.get("licenseKey")
        or result.get("key")
        or result.get("vipKey")
        or result.get("license")
        or ""
    ).strip()


def _is_paid_status(result: Dict[str, Any]) -> bool:
    return str(result.get("status", "")).lower() in _PAID_STATUSES

# Per-user cooldown for /freescript so someone can't spam-generate Link4M links
# (each call burns a real API quota hit against LINK4M_TOKEN).
FREESCRIPT_COOLDOWN_SEC = 600  # 10 minutes
_freescript_last_request: Dict[int, float] = {}

# Background poll: check every 10s for up to 30 minutes before giving up (manual "Check" button still works after)
POLL_INTERVAL_SEC = 10
POLL_MAX_ATTEMPTS = 180
RECONCILE_INTERVAL_SEC = 60
_TRANSFER_CODE_RE = re.compile(r"^VIP\d{3,10}$", re.IGNORECASE)


def _select_vietqr_transfer_code(invoice: Dict[str, Any]) -> str:
    """Use the exact transfer content shown to the buyer when it matches the
    SePay VIP recognition rule. Some backend payloads expose an internal
    transferCode (DHxxxxxx) plus a buyer-facing memo (VIPxxxxxx); checking with
    the internal code leaves VIP payments pending forever.
    """
    memo = str(invoice.get("memo") or "").strip().upper()
    transfer_code = str(invoice.get("transferCode") or "").strip().upper()
    if _TRANSFER_CODE_RE.match(memo):
        if transfer_code and transfer_code != memo:
            logger.warning("VietQR payload transferCode/memo mismatch: transferCode=%s memo=%s; using memo", transfer_code, memo)
        return memo
    return transfer_code or memo


async def get_plan_pricing(plan: str) -> Dict[str, Any]:
    """Pricing for `plan`, live-overridden with the flash-sale price for the
    30-day plan when one is active right now. This is for display and for
    picking which VND amount to request - the backend independently
    re-checks the sale window at actual purchase time regardless of what
    this says, so a stale/wrong read here can never grant an unearned
    discount, only (rarely) show/request the normal price a few seconds
    into or out of a window."""
    info = dict(VIP_PLANS[plan])
    info["on_sale"] = False
    if plan == "1month":
        sale = await get_flash_sale_status()
        if sale.get("active") and sale.get("plan") == "1month":
            info["usd"] = str(sale["priceUsd"])
            info["vnd"] = sale["priceVnd"]
            info["on_sale"] = True
    return info


def format_plan_button_label(plan: str, info: Dict[str, Any]) -> str:
    if info.get("on_sale"):
        original = VIP_PLANS[plan]["usd"]
        return f"🔥 30 Days - ${original}→${info['usd']} FLASH SALE!"
    return info["label"]


async def build_plan_keyboard() -> InlineKeyboardMarkup:
    plan_2day = await get_plan_pricing("2day")
    plan_1month = await get_plan_pricing("1month")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=format_plan_button_label('2day', plan_2day), callback_data="vipbuy:2day",
            icon_custom_emoji_id=config.CHOOSE_ID,
        )],
        [InlineKeyboardButton(
            text=format_plan_button_label('1month', plan_1month), callback_data="vipbuy:1month",
            icon_custom_emoji_id=config.CHOOSE_ID,
        )],
    ])


def build_method_keyboard(plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Pay with USDT (Crypto)", callback_data=f"vippay:{plan}:usdt",
            icon_custom_emoji_id=config.CARD_ID,
        )],
        [InlineKeyboardButton(
            text="Pay with Bank Transfer (VietQR/SePay)", callback_data=f"vippay:{plan}:vietqr",
            icon_custom_emoji_id=config.BANK_ID,
        )],
        [InlineKeyboardButton(text="Back", callback_data="vipbuy:menu", icon_custom_emoji_id=config.BACK_ID)],
    ])


async def send_vip_plan_menu(bot: Bot, chat_id: int):
    """Shows the VIP plan picker. Entry point for the "Buy VIP Key" deep link."""
    plan_1month = await get_plan_pricing("1month")
    month_line = (
        f"<b>🔥 30 Days:</b> <s>${VIP_PLANS['1month']['usd']}</s> <b>${plan_1month['usd']} FLASH SALE!</b>"
        if plan_1month["on_sale"] else
        f"{emoji_mgr.vip} <b>30 Days:</b> ${VIP_PLANS['1month']['usd']} USD"
    )
    text = (
        f"{emoji_mgr.vip} <b>BUY VIP KEY - DRAGON CITY</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.choose} Choose a plan below. Pay with crypto (USDT) or bank transfer (VietQR) - "
        f"your key is delivered <b>automatically</b> right after payment is confirmed.\n\n"
        f"<b>💎 2 Days:</b> $1 USD\n"
        f"{month_line}\n\n"
        f"{emoji_mgr.diamond} <i>Need help?</i> DM {emoji_mgr.vip} {emoji_mgr.tele_logo} :@wolfmodyt"
    )
    await safe_send_message(
        bot, chat_id, emoji_mgr.format_msg(text),
        parse_mode="HTML", reply_markup=await build_plan_keyboard()
    )


async def _get_display_username(bot: Bot, chat_id: int) -> str:
    """Best-effort Telegram username for `chat_id` (a private-chat ID, which for
    a DM is the same as the user's own ID). Falls back to first name, then the
    raw ID, if the user has no @username set."""
    try:
        chat = await bot.get_chat(chat_id)
        return chat.username or chat.first_name or str(chat_id)
    except Exception as e:
        logger.warning("Could not resolve username for chat %s: %s", chat_id, e)
        return str(chat_id)


async def deliver_vip_key(bot: Bot, chat_id: int, dedup_key: str, license_key: str, duration: str):
    """Sends the purchased VIP key to the buyer. Safe to call more than once (deduped)."""
    if dedup_key in _delivered_orders:
        return
    _delivered_orders.add(dedup_key)

    username = await _get_display_username(bot, chat_id)
    activation_pair = f"{html.escape(username)},{html.escape(license_key)}"
    text = (
        f"{emoji_mgr.vip} <b>PAYMENT SUCCESSFUL!</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.star} <b>Plan:</b> VIP {duration}\n"
        f"{emoji_mgr.key} <b>Your VIP Key</b> (username,key - tap to reveal):\n<tg-spoiler>{activation_pair}</tg-spoiler>\n\n"
        f"{emoji_mgr.fire} <b>Download VIP Script:</b> <a href=\"{config.VIP_SCRIPT_URL}\">Click here</a>\n"
        f"{emoji_mgr.diamond} <b>Activate at:</b> <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n"
        f"{emoji_mgr.star} <i>Need help activating?</i> DM {emoji_mgr.vip} :@wolfmodyt"
    )
    await safe_send_message(bot, chat_id, emoji_mgr.format_msg(text), parse_mode="HTML", disable_web_page_preview=True)
    logger.info("VIP key delivered for order %s to chat %s", dedup_key, chat_id)


async def deliver_vip_order(bot: Bot, order: Dict[str, Any], license_key: str) -> bool:
    """DB-backed idempotent delivery. Safe across restart/manual/reconcile races."""
    order_id = int(order["id"])
    claimed = await db.claim_vip_order_delivery(order_id, license_key)
    if not claimed:
        logger.info("VIP order %s already delivered or claimed by another task", order_id)
        return False

    dedup_key = f"{order.get('method')}:{order.get('pending_id') or order.get('order_id') or order_id}"
    await deliver_vip_key(bot, int(order["chat_id"]), dedup_key, license_key, order.get("duration") or "VIP")
    logger.info("VIP order %s marked delivered in DB", order_id)
    return True


async def check_and_deliver_vip_order(bot: Bot, order: Dict[str, Any]) -> Optional[str]:
    order_id = int(order["id"])
    method = order.get("method")
    try:
        if method == "vietqr":
            result = await check_vietqr_order(str(order.get("pending_id") or ""), str(order.get("transfer_code") or ""))
        elif method == "usdt":
            result = await check_vip_order(str(order.get("order_id") or ""))
        else:
            logger.error("VIP order %s has unknown method: %s", order_id, method)
            await db.mark_vip_order_checked(order_id, "check_error")
            return "error"
    except Exception as e:
        logger.error("VIP order %s check exception: %s", order_id, e)
        await db.mark_vip_order_checked(order_id, "check_error")
        return "error"

    if not result:
        logger.error("VIP order %s check failed: method=%s pending_id=%s transfer_code=%s order_id=%s", order_id, method, order.get("pending_id"), order.get("transfer_code"), order.get("order_id"))
        await db.mark_vip_order_checked(order_id, "check_error")
        return "error"

    status = str(result.get("status") or "pending").lower()

    # Backend returned 404 → order deleted/expired on server
    if status == "not_found":
        logger.info("VIP order %s not found on backend (expired/deleted), marking expired", order_id)
        await db.mark_vip_order_checked(order_id, "expired")
        return "expired"

    if _is_paid_status(result):
        license_key = _extract_license_key(result)
        if license_key:
            await db.mark_vip_order_checked(order_id, status, license_key)
            await deliver_vip_order(bot, order, license_key)
            return "delivered"
        logger.error("VIP order %s is paid but backend returned no key: %s", order_id, result)
        await db.mark_vip_order_checked(order_id, "paid_no_key")
        await safe_send_message(
            bot, int(order["chat_id"]),
            emoji_mgr.format_msg(f"{emoji_mgr.warn} <b>Payment found, but backend did not return a VIP key.</b>\nPlease contact {emoji_mgr.vip} :@wolfmodyt with code <code>{html.escape(str(order.get('transfer_code') or order.get('order_id') or order_id))}</code>."),
            parse_mode="HTML",
        )
        return "paid_no_key"

    await db.mark_vip_order_checked(order_id, status)
    logger.info("VIP order %s not paid yet: status=%s result=%s", order_id, status, result)
    return status


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

        if result and _is_paid_status(result):
            license_key = _extract_license_key(result)
            if license_key:
                await deliver_vip_key(bot, chat_id, dedup_key, license_key, duration)
                return
            logger.error("USDT order %s is paid but response has no key: %s", order_id, result)
            return

    logger.info("USDT order %s polling timed out after %s attempts (manual check-button still works)", order_id, POLL_MAX_ATTEMPTS)


async def poll_db_vip_order(bot: Bot, db_order_id: int):
    for _ in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SEC)
        order = await db.get_vip_order(db_order_id)
        if not order or order.get("delivered_at"):
            return
        outcome = await check_and_deliver_vip_order(bot, order)
        if outcome in {"delivered", "paid_no_key", "expired"}:
            return

    logger.info("VIP DB order %s polling timed out after %s attempts", db_order_id, POLL_MAX_ATTEMPTS)


async def vip_reconcile_loop(bot: Bot):
    while True:
        try:
            orders = await db.list_pending_vip_orders(limit=50)
            for order in orders:
                if order.get("delivered_at"):
                    continue
                await check_and_deliver_vip_order(bot, order)
        except Exception as e:
            logger.error("VIP reconcile loop error: %s", e)
        await asyncio.sleep(RECONCILE_INTERVAL_SEC)


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

        if result and _is_paid_status(result):
            license_key = _extract_license_key(result)
            if license_key:
                await deliver_vip_key(bot, chat_id, dedup_key, license_key, duration)
                return
            logger.error("VietQR order %s is paid but response has no key: %s", pending_id, result)
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
    if plan not in VIP_PLANS:
        await callback.answer("Invalid plan.", show_alert=True)
        return

    plan_info = await get_plan_pricing(plan)
    await callback.answer()
    text = (
        f"{emoji_mgr.vip} <b>{format_plan_button_label(plan, plan_info)}</b> {emoji_mgr.vip}\n\n"
        f"{emoji_mgr.choose} Choose a payment method:"
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
    if plan not in VIP_PLANS:
        await callback.answer("Invalid plan.", show_alert=True)
        return
    plan_info = await get_plan_pricing(plan)

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
        db_order_id = await db.upsert_vip_order(
            method="usdt",
            chat_id=chat_id,
            user_id=user.id if user else 0,
            username=(user.username or "") if user else "",
            plan=plan,
            duration=plan_info["duration"],
            amount=int(float(invoice.get("amountUsd", plan_info["usd"])) * 100),
            order_id=order_id,
            status="created",
        )
        logger.info("VIP USDT order saved: db_id=%s order_id=%s chat_id=%s", db_order_id, order_id, chat_id)
        qr_bytes = get_qr_image_bytes(invoice.get("qrCode"), invoice_url)

        caption = (
            f"{emoji_mgr.vip} <b>PAY VIP KEY - {plan_info['duration'].upper()} (USDT)</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.moneybag} <b>Amount:</b> <code>${invoice.get('amountUsd', plan_info['usd'])} USD</code> (USDT - BEP20 network)\n"
            f"{emoji_mgr.memo} <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n\n"
            f"{emoji_mgr.warn} Scan the QR code or tap the button below to pay. Your key is delivered "
            f"<b>automatically</b> right after payment is confirmed (usually within 1-5 minutes).\n\n"
            f"{emoji_mgr.diamond} <i>This invoice expires in 2 hours.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Open Payment Page", url=invoice_url, icon_custom_emoji_id=config.OPENLINK_ID)],
            [InlineKeyboardButton(
                text="I've Paid - Check Now", callback_data=f"vipcheck:usdt:{order_id}",
                icon_custom_emoji_id=config.CHECKPAID_ID,
            )],
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

        asyncio.create_task(poll_db_vip_order(bot, db_order_id))

    elif method == "vietqr":
        await callback.answer("⏳ Creating your payment order...")
        username = f"TG-{user.id}" if user else "TG-Unknown"
        invoice = await create_vietqr_invoice(username, plan_info["vnd"])
        # If the sale window closed in the few seconds between opening this
        # menu and tapping "Pay", the backend silently falls back to the
        # normal VND tier - re-fetch what it actually stored so the caption
        # below (which already renders invoice['amount']) is never wrong.
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
        transfer_code = _select_vietqr_transfer_code(invoice)
        invoice["memo"] = transfer_code
        qr_url = invoice.get("qrUrl")
        db_order_id = await db.upsert_vip_order(
            method="vietqr",
            chat_id=chat_id,
            user_id=user.id if user else 0,
            username=(user.username or "") if user else "",
            plan=plan,
            duration=plan_info["duration"],
            amount=int(invoice.get("amount", plan_info["vnd"])),
            pending_id=pending_id,
            transfer_code=transfer_code,
            status="created",
        )
        logger.info("VIP VietQR order saved: db_id=%s pending_id=%s transfer_code=%s chat_id=%s", db_order_id, pending_id, transfer_code, chat_id)

        caption = (
            f"{emoji_mgr.vip} <b>PAY VIP KEY - {plan_info['duration'].upper()} (BANK TRANSFER)</b> {emoji_mgr.vip}\n\n"
            f"{emoji_mgr.moneybag} <b>Amount:</b> <code>{invoice['amount']:,} VND</code>\n"
            f"{emoji_mgr.bank} <b>Bank:</b> {html.escape(invoice.get('bankName', ''))}\n"
            f"{emoji_mgr.uid} <b>Account Name:</b> {html.escape(invoice.get('accountName', ''))}\n"
            f"{emoji_mgr.card} <b>Account Number:</b> <code>{html.escape(invoice.get('accountNo', ''))}</code>\n"
            f"{emoji_mgr.memo} <b>Transfer Content (required):</b> <code>{html.escape(invoice['memo'])}</code>\n\n"
            f"{emoji_mgr.warn} Scan the QR code with your banking app, or transfer manually using the info above "
            f"(the transfer content <b>must</b> match exactly). Your key is delivered <b>automatically</b> right "
            f"after payment is confirmed (usually within 1-2 minutes).\n\n"
            f"{emoji_mgr.diamond} <i>This order expires in 5 minutes.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="I've Paid - Check Now", callback_data=f"vipcheck:vietqr:{pending_id}:{transfer_code}",
                icon_custom_emoji_id=config.CHECKPAID_ID,
            )],
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

        asyncio.create_task(poll_db_vip_order(bot, db_order_id))


@router.callback_query(F.data.startswith("vipcheck:"))
async def on_vip_check(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":", 2)
    method = parts[1]
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id

    if method == "usdt":
        order_id = parts[2]
        order = await db.get_vip_order_by_order_id(order_id, chat_id)
        dedup_key = f"usdt:{order_id}"
        if dedup_key in _delivered_orders or (order and order.get("delivered_at")):
            await callback.answer("✅ Key already delivered, please check the message above!", show_alert=True)
            return

        await callback.answer("🔍 Checking payment...")
        if order:
            outcome = await check_and_deliver_vip_order(bot, order)
            if outcome == "delivered":
                return
            if outcome == "paid_no_key":
                await callback.answer("✅ Payment found, but key was not returned. Please contact @wolfmodyt.", show_alert=True)
                return
            if outcome == "error":
                await callback.answer("❌ Could not check status right now, please try again later.", show_alert=True)
                return
            await callback.answer("⏳ Payment not received yet. Please wait a few minutes after paying and try again.", show_alert=True)
            return

        result = await check_vip_order(order_id)
        if not result:
            await callback.answer("❌ Could not check status right now, please try again later.", show_alert=True)
            return

        if _is_paid_status(result):
            license_key = _extract_license_key(result)
            if license_key:
                await deliver_vip_key(bot, chat_id, dedup_key, license_key, "VIP")
            else:
                logger.error("USDT order %s is paid but response has no key: %s", order_id, result)
                await callback.answer("✅ Payment found, but key was not returned. Please contact @wolfmodyt.", show_alert=True)
        else:
            await callback.answer("⏳ Payment not received yet. Please wait a few minutes after paying and try again.", show_alert=True)

    elif method == "vietqr":
        pending_id, transfer_code = parts[2].split(":", 1)
        order = await db.get_vip_order_by_transfer_code(transfer_code, chat_id)
        dedup_key = f"vietqr:{pending_id}"
        if dedup_key in _delivered_orders or (order and order.get("delivered_at")):
            await callback.answer("✅ Key already delivered, please check the message above!", show_alert=True)
            return

        await callback.answer("🔍 Checking payment...")
        if order:
            outcome = await check_and_deliver_vip_order(bot, order)
            if outcome == "delivered":
                return
            if outcome == "paid_no_key":
                await callback.answer("✅ Payment found, but key was not returned. Please contact @wolfmodyt.", show_alert=True)
                return
            if outcome == "expired":
                await callback.answer("⌛ This order has expired. Please create a new one with /start buyvip.", show_alert=True)
                return
            if outcome == "error":
                await callback.answer("❌ Could not check status right now, please try again later.", show_alert=True)
                return
            await callback.answer("⏳ Payment not received yet. Please wait a few minutes after transferring and try again.", show_alert=True)
            return

        result = await check_vietqr_order(pending_id, transfer_code)
        if not result:
            await callback.answer("❌ Could not check status right now, please try again later.", show_alert=True)
            return

        status = result.get("status")
        if _is_paid_status(result):
            license_key = _extract_license_key(result)
            if license_key:
                await deliver_vip_key(bot, chat_id, dedup_key, license_key, "VIP")
            else:
                logger.error("VietQR order %s is paid but response has no key: %s", pending_id, result)
                await callback.answer("✅ Payment found, but key was not returned. Please contact @wolfmodyt.", show_alert=True)
        elif status == "expired":
            await callback.answer("⌛ This order has expired. Please create a new one with /start buyvip.", show_alert=True)
        else:
            await callback.answer("⏳ Payment not received yet. Please wait a few minutes after transferring and try again.", show_alert=True)


async def check_vip_by_transfer_code(message: Message, bot: Bot, transfer_code: str):
    transfer_code = transfer_code.strip().upper()
    order = await db.get_vip_order_by_transfer_code(transfer_code, message.chat.id)
    if not order:
        logger.error("VIP transfer code %s not found in bot DB for chat %s", transfer_code, message.chat.id)
        await message.answer(
            emoji_mgr.format_msg(
                f"{emoji_mgr.error} <b>Order not found in bot database.</b>\n"
                f"Code: <code>{html.escape(transfer_code)}</code>\n"
                f"Please send payment screenshot to {emoji_mgr.vip} :@wolfmodyt."
            ),
            parse_mode="HTML",
        )
        return

    if order.get("delivered_at"):
        await message.answer("✅ Key already delivered. Please check messages above.")
        return

    await message.answer("🔍 Checking payment now...")
    outcome = await check_and_deliver_vip_order(bot, order)
    if outcome == "delivered":
        return
    if outcome == "paid_no_key":
        await message.answer("✅ Payment found, but backend did not return a key. Please contact @wolfmodyt.")
        return
    if outcome == "expired":
        await message.answer("⌛ This order expired. If money left your bank, please contact @wolfmodyt with payment screenshot.")
        return
    if outcome == "error":
        await message.answer("❌ Could not check status right now. Please try again later.")
        return
    await message.answer("⏳ Payment not received yet. Wait 1-2 minutes after bank transfer, then send the code again.")


@router.message(Command("checkvip"))
async def on_checkvip_command(message: Message, bot: Bot):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not _TRANSFER_CODE_RE.match(parts[1].strip()):
        await message.answer("Usage: /checkvip VIP464402")
        return
    await check_vip_by_transfer_code(message, bot, parts[1])


@router.message(F.chat.type == "private", F.text.regexp(_TRANSFER_CODE_RE.pattern))
async def on_transfer_code_message(message: Message, bot: Bot):
    await check_vip_by_transfer_code(message, bot, message.text or "")


# ── Free Script (Link4M ad-gate unlock) ──────────────────────────────────────

async def deliver_free_script(bot: Bot, chat_id: int):
    """Thanks the user and hands over the free script link. Called once the user
    completes the Link4M ad-gate and returns via the /start freescript_<uid> deep link.
    This flow always runs in DM (see send_free_script_prompt's docstring), so
    chat_id doubles as the user's Telegram user ID for the free-key request."""
    key_result = await generate_free_key(chat_id)
    if key_result.get("success") and key_result.get("key"):
        username = await _get_display_username(bot, chat_id)
        activation_pair = f"{html.escape(username)},{html.escape(key_result['key'])}"
        key_line = f"{emoji_mgr.key} <b>Your Free Key</b> (username,key - tap to reveal):\n<tg-spoiler>{activation_pair}</tg-spoiler>\n"
    else:
        key_line = f"{emoji_mgr.warn} <i>{html.escape(key_result.get('error') or 'Free key unavailable right now.')}</i>\n"

    text = (
        f"{emoji_mgr.check} <b>THANK YOU!</b> {emoji_mgr.check}\n\n"
        f"{emoji_mgr.star} You've unlocked the <b>Dragon City Free Script</b>.\n\n"
        f"{emoji_mgr.fire} <b>Download Free Script:</b> <a href=\"{config.FREE_SCRIPT_URL}\">Click here</a>\n"
        f"{emoji_mgr.diamond} <b>Activate/Use at:</b> <a href=\"https://www.wolfmod.xyz/dragon-city\">https://www.wolfmod.xyz/dragon-city</a>\n"
        f"{key_line}\n"
        f"{emoji_mgr.vip} <i>Want the full VIP feature set instead?</i> Type <code>/start buyvip</code>"
    )
    await safe_send_message(bot, chat_id, emoji_mgr.format_msg(text), parse_mode="HTML", disable_web_page_preview=True)
    logger.info("Free script delivered to chat %s (key_success=%s)", chat_id, key_result.get("success"))


async def send_free_script_prompt(bot: Bot, chat_id: int, user_id: int):
    """Shows "Get Free Script" ad-gate unlock buttons (Link4M + Linkvertise).
    Works from any chat, but the actual unlock always happens in DM (both
    services redirect back to a /start deep link, which only fires in a
    private chat)."""
    now = time.time()
    last = _freescript_last_request.get(user_id, 0)
    if now - last < FREESCRIPT_COOLDOWN_SEC:
        wait_min = max(1, round((FREESCRIPT_COOLDOWN_SEC - (now - last)) / 60))
        await safe_send_message(
            bot, chat_id,
            emoji_mgr.format_msg(
                f"{emoji_mgr.warn} <b>Please wait {wait_min} more minute(s)</b> before requesting another free script link."
            ),
            parse_mode="HTML",
        )
        return
    _freescript_last_request[user_id] = now

    bot_info = await bot.get_me()
    deep_link = f"https://t.me/{bot_info.username}?start=freescript_{user_id}"

    # Link4M: server-side shortener, no page needed - the button opens Telegram directly.
    short_url = await shorten_link4m(deep_link)
    link4m_url = short_url or deep_link

    # Linkvertise: can only gate clicks on a page with its script embedded, so this
    # opens a small wolfmod.xyz bridge page whose own "Continue" link is what
    # actually gets ad-gated before it hands the user back to the deep link.
    linkvertise_url = (
        f"{config.WOLFMOD_API_BASE_URL}/free-script-unlock.html"
        f"?uid={user_id}&bot={bot_info.username}"
    )

    text = (
        f"{emoji_mgr.check} <b>GET FREE DRAGON CITY SCRIPT</b> {emoji_mgr.check}\n\n"
        f"{emoji_mgr.star} Tap either button below and complete the short unlock step "
        f"(a few seconds of ads) - you'll be redirected back here automatically once done, "
        f"and the free script link will be sent to you instantly.\n\n"
        f"{emoji_mgr.warn} <i>Make sure pop-ups aren't blocked so the redirect can complete.</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Unlock via Link4M", url=link4m_url, icon_custom_emoji_id=config.BACK_ID)],
        [InlineKeyboardButton(text="Unlock via Linkvertise", url=linkvertise_url, icon_custom_emoji_id=config.BACK_ID)],
    ])
    await safe_send_message(bot, chat_id, emoji_mgr.format_msg(text), parse_mode="HTML", reply_markup=keyboard)


async def send_freekey_entry_button(bot: Bot, chat_id: int):
    """Single "Free Key" button (shown after the guide video) - tapping it
    reveals the actual Link4M/Linkvertise unlock buttons via send_free_script_prompt,
    same two-step pattern as "BUY VIP NOW" -> plan menu."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Free Key", callback_data="show_freekey_links", icon_custom_emoji_id=config.KEY_ID)]
    ])
    await safe_send_message(
        bot, chat_id,
        emoji_mgr.format_msg(f"{emoji_mgr.key} <b>Tap below to get your Free Key</b>"),
        parse_mode="HTML", reply_markup=keyboard,
    )


@router.callback_query(F.data == "show_freekey_links")
async def on_freekey_button(callback: CallbackQuery, bot: Bot):
    if not callback.message or not callback.from_user:
        await callback.answer()
        return
    await callback.answer()
    await send_free_script_prompt(bot, callback.message.chat.id, callback.from_user.id)


@router.callback_query(F.data == "show_buyvip_menu")
async def on_buyvip_button(callback: CallbackQuery, bot: Bot):
    if not callback.message:
        await callback.answer()
        return
    await callback.answer()
    await send_vip_plan_menu(bot, callback.message.chat.id)


@router.message(Command("freescript"))
async def cmd_free_script(message: Message, bot: Bot):
    """Entry point for the "Get Free Script" flow."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return
    await send_free_script_prompt(bot, message.chat.id, user_id)
