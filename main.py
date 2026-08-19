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
from handlers.callback_handlers import router as callback_router
from handlers.member_handlers import router as member_router
from handlers.message_handlers import router as message_router

async def set_bot_commands(bot: Bot):
    """Sets standard command list in Telegram menu for regular users and admins"""
    try:
        user_commands = [
            BotCommand(command="start", description="Khởi động & thông tin bot"),
            BotCommand(command="help", description="Hướng dẫn sử dụng & danh sách lệnh"),
            BotCommand(command="warns", description="Xem số cảnh cáo của bản thân"),
        ]
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

        admin_commands = [
            BotCommand(command="settings", description="Bảng cài đặt bảo vệ nhóm"),
            BotCommand(command="warn", description="Cảnh cáo thành viên (reply)"),
            BotCommand(command="unwarn", description="Xoá cảnh cáo (reply)"),
            BotCommand(command="mute", description="Cấm chat thành viên (reply)"),
            BotCommand(command="unmute", description="Mở cấm chat (reply)"),
            BotCommand(command="kick", description="Trục xuất khỏi nhóm (reply)"),
            BotCommand(command="ban", description="Cấm vĩnh viễn (reply)"),
            BotCommand(command="stats", description="Xem thống kê vi phạm"),
            BotCommand(command="get_emoji", description="Lấy ID Custom Emoji VIP"),
            BotCommand(command="help", description="Toàn bộ danh sách lệnh"),
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
        print("\n[ERROR] Vui lòng cấu hình BOT_TOKEN trong file .env hoặc biến môi trường Railway!")
        print("Ví dụ: BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ\n")
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
    dp.include_router(admin_router)
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
    print(f"🛡️  TELEGRAM GUARD BOT ĐANG HOẠT ĐỘNG! 👑")
    print(f"• Username : @{bot_user.username}")
    print(f"• Bot ID   : {bot_user.id}")
    print(f"• Database : {config.DATABASE_PATH}")
    print(f"• VIP Emoji: Sẵn sàng hỗ trợ Telegram Premium Custom Emoji")
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
