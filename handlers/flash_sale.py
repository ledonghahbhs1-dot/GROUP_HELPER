import asyncio

from aiogram import Bot

from database.db import db
from handlers.member_handlers import build_buyvip_keyboard
from handlers.vip_handlers import VIP_PLANS
from utils.emoji_helper import emoji_mgr, safe_send_message
from utils.logger import logger
from utils.wolfmod_api import get_flash_sale_status

# Cheap GET against the backend; frequent enough that a window's start is
# announced within a minute of actually opening.
POLL_INTERVAL_SEC = 60


async def _broadcast_sale_start(bot: Bot, price_usd: str):
    """Announces a newly-opened flash sale to every group the bot moderates.
    The backend is the sole authority on price/timing (see get_flash_sale_status) -
    this only decides *when* to post, never what to charge."""
    chat_ids = await db.get_all_group_chat_ids()
    keyboard = await build_buyvip_keyboard(bot, "group")
    original_usd = VIP_PLANS["1month"]["usd"]
    text = (
        f"{emoji_mgr.sale} <b>FLASH SALE - 2 HOURS ONLY!</b> {emoji_mgr.sale}\n\n"
        f"{emoji_mgr.fire} <b>30-Day VIP Key:</b> <s>${original_usd}</s> <b>${price_usd}</b>\n"
        f"{emoji_mgr.warn} <i>Ends in 2 hours - grab it before it's gone!</i> "
        f"<i>(2-Day plan not included)</i>\n\n"
        f"{emoji_mgr.choose} Tap below to buy now at this price."
    )
    sent = 0
    for chat_id in chat_ids:
        try:
            await safe_send_message(bot, chat_id, emoji_mgr.format_msg(text), parse_mode="HTML", reply_markup=keyboard)
            sent += 1
        except Exception as e:
            logger.warning("Flash sale announcement failed for chat %s: %s", chat_id, e)
        await asyncio.sleep(0.1)  # gentle pacing across many groups
    logger.info("Flash sale announced to %d/%d group(s) at $%s", sent, len(chat_ids), price_usd)


async def flash_sale_loop(bot: Bot):
    """Polls the backend's flash-sale status and announces the moment a sale
    window opens (transition from inactive -> active). Runs for the lifetime
    of the bot process."""
    was_active = False
    while True:
        try:
            status = await get_flash_sale_status()
            is_active = bool(status.get("active"))
            if is_active and not was_active:
                await _broadcast_sale_start(bot, str(status.get("priceUsd", "5.99")))
            was_active = is_active
        except Exception as e:
            logger.error("flash_sale_loop error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SEC)
