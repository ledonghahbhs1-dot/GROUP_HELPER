"""
SePay webhook receiver.

SePay sends a POST with transaction data when a bank transfer is detected.
This handler matches the transfer content (VIPxxxxxx) to a pending order in
the bot's DB and triggers an immediate check+deliver cycle via the wolfmod.xyz
backend, so the buyer gets their key within seconds of the bank confirming
the transfer — no need to wait for the next 60-second reconcile poll.
"""

import re
from aiohttp import web
from aiogram import Bot

from database.db import db
from handlers.vip_handlers import check_and_deliver_vip_order
from utils.logger import logger

_VIP_CODE_RE = re.compile(r"VIP\d{3,10}", re.IGNORECASE)


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"success": True, "message": "SePay webhook is ready"})


async def _sepay_webhook(request: web.Request) -> web.Response:
    """Handle POST from SePay when a bank transfer is detected."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    content = (
        str(data.get("content") or data.get("transactionContent") or data.get("description") or "")
        .upper()
    )
    amount = data.get("transferAmount") or data.get("amount") or 0

    logger.info("SePay webhook received: amount=%s content=%s", amount, content)

    # Extract VIP transfer code from transaction content
    match = _VIP_CODE_RE.search(content)
    if not match:
        logger.info("SePay webhook: no VIP code in content, ignoring")
        return web.json_response({"success": True, "message": "Ignored (no VIP code)"})

    transfer_code = match.group(0).upper()
    logger.info("SePay webhook: matched transfer_code=%s", transfer_code)

    # Find order in DB
    order = await db.get_vip_order_by_transfer_code(transfer_code)
    if not order:
        logger.warning("SePay webhook: order not found in DB for transfer_code=%s", transfer_code)
        return web.json_response({"success": True, "message": "Order not found in bot DB"})

    order_status = str(order.get("status") or "").lower()
    if order.get("delivered_at") or order_status in ("delivered", "expired"):
        logger.info("SePay webhook: order %s already %s, skipping", order["id"], order_status or "delivered")
        return web.json_response({"success": True, "message": f"Order already {order_status or 'delivered'}"})

    # Trigger immediate check+deliver via backend
    bot: Bot = request.app["bot"]
    outcome = await check_and_deliver_vip_order(bot, order)
    logger.info("SePay webhook: order %s check outcome=%s", order["id"], outcome)

    return web.json_response({"success": True, "message": f"Processed: {outcome}"})


def create_sepay_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/sepay-webhook", _health)
    app.router.add_post("/sepay-webhook", _sepay_webhook)
    app.router.add_get("/sepay-webhook/", _health)
    app.router.add_post("/sepay-webhook/", _sepay_webhook)
    # Health check for Railway
    app.router.add_get("/", _health)
    return app