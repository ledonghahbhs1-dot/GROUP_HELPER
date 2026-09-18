import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllChatAdministrators

import config
from database.db import db
from utils.emoji_helper import emoji_mgr
from utils.logger import logger
from filters.spam_filter import spam_filter

from handlers.admin_handlers import router as admin_router
from handlers.vip_handlers import router as vip_router
from handlers.callback_handlers import router as callback_router
from handlers.member_handlers import router as member_router
from handlers.message_handlers import router as message_router

async def set_bot_commands(bot: Bot):
    """Sets standard command list in Telegram menu for regular users and admins"""
    try:
        user_commands = [
            BotCommand(command="start", description="Start & bot information"),
            BotCommand(command="help", description="Help guide & commands list"),
            BotCommand(command="features", description="VIP & Free script features list"),
            BotCommand(command="price", description="VIP key pricing & packages"),
            BotCommand(command="pay", description="Payment methods info"),
            BotCommand(command="script", description="Dragon City Tool & Script link"),
            BotCommand(command="warns", description="Check warning status"),
        ]
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

        admin_commands = [
            BotCommand(command="settings", description="Group security & rules panel"),
            BotCommand(command="banlist", description="Banned members list & 1-click unban"),
            BotCommand(command="features", description="VIP & Free script features list"),
            BotCommand(command="price", description="VIP key pricing & packages"),
            BotCommand(command="pay", description="Payment methods info"),
            BotCommand(command="script", description="Dragon City Tool & Script link"),
            BotCommand(command="warn", description="Warn member (reply/ID/@username)"),
            BotCommand(command="unwarn", description="Remove warning (reply/ID/@username)"),
            BotCommand(command="mute", description="Mute member (reply/ID/@username)"),
            BotCommand(command="unmute", description="Unmute member (reply/ID/@username)"),
            BotCommand(command="kick", description="Kick member (reply/ID/@username)"),
            BotCommand(command="ban", description="Ban member permanently (reply/ID/@username)"),
            BotCommand(command="unban", description="Unban member (ID/@username)"),
            BotCommand(command="stats", description="View security violation statistics"),
            BotCommand(command="get_emoji", description="Extract Custom Emoji VIP IDs"),
            BotCommand(command="help", description="Full administrator commands list"),
        ]
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
    except Exception as e:
        logger.warning("Could not set bot commands: %s", e)

async def periodic_spam_cleanup():
    """Background task to free memory from spam filter cache"""
    while True:
        await asyncio.sleep(300) # Every 5 minutes
        spam_filter.cleanup_old_data()

async def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN.startswith("1234567890:"):
        logger.error("BOT_TOKEN is missing or not configured! Please set BOT_TOKEN in .env or Railway environment variables.")
        print("\n[ERROR] Please configure BOT_TOKEN in .env file or Railway environment variables!")
        print("Example: BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ\n")
        return

    logger.info("Starting Telegram Guard Bot...")

    # 1. Initialize Database
    await db.init_db()

    # 2. Load Custom Emojis
    await emoji_mgr.load_emojis()

    # 3. Setup Bot and Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 4. Register Handlers in priority order
    # vip_router must come before callback_router: callback_handlers.py has a
    # catch-all @router.callback_query() with no filter that would otherwise
    # swallow the "vipbuy:"/"vipcheck:" callback buttons first.
    dp.include_router(admin_router)
    dp.include_router(vip_router)
    dp.include_router(callback_router)
    dp.include_router(member_router)
    dp.include_router(message_router)

    # 5. Startup Actions
    bot_user = await bot.get_me()
    logger.info("Bot authenticated successfully: @%s (%s)", bot_user.username, bot_user.id)
    await set_bot_commands(bot)

    # Start periodic background cleanup task
    asyncio.create_task(periodic_spam_cleanup())

    print("\n" + "=" * 55)
    print(f"🛡️  TELEGRAM GUARD BOT IS RUNNING! 👑")
    print(f"• Username : @{bot_user.username}")
    print(f"• Bot ID   : {bot_user.id}")
    print(f"• Database : {config.DATABASE_PATH}")
    print(f"• VIP Emoji: Telegram Premium Custom Emoji Ready")
    print(f"• Scam Detect: ✅ ENABLED (140+ keywords - 13 languages)")
    print("=" * 55 + "\n")

    # 6. Start Polling
    try:
        await dp.start_polling(bot, allowed_updates=["message", "chat_member", "callback_query"])
    finally:
        await bot.session.close()
        logger.info("Bot stopped gracefully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application exited by user.")
