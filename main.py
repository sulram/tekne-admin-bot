"""
Tekne Admin Bot - Main entry point
Telegram bot for proposal generation using Claude AI
"""

import logging
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN, ALLOWED_USERS
from bot.handlers import (
    hello,
    help_command,
    cost_command,
    start_proposal,
    reset_proposal,
    reset_daily,
    reset_all,
    handle_text_message,
    handle_photo,
    handle_audio,
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suppress httpx INFO logs to avoid flooding
logging.getLogger("httpx").setLevel(logging.WARNING)

# Log access control configuration
if ALLOWED_USERS:
    logger.info(f"Access control enabled for {len(ALLOWED_USERS)} users: {ALLOWED_USERS}")
else:
    logger.warning("⚠️  ALLOWED_USERS not set - bot is open to all users!")


async def post_init(application) -> None:
    """Set bot commands in Telegram UI with organized categories"""
    # Main commands - shown in the menu (top 3 most used)
    commands = [
        BotCommand("proposal", "✨ Criar ou editar propostas"),
        BotCommand("reset", "🔄 Nova sessão (limpar conversa)"),
        BotCommand("help", "📖 Ver todos os comandos"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("✅ Bot commands set successfully")
    except Exception as e:
        logger.warning(f"⚠️  Could not set bot commands (will retry later): {str(e)}")
        # Don't fail startup - commands will still work, just won't show in UI


# Build application
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

# Command handlers
app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("cost", cost_command))
app.add_handler(CommandHandler("proposal", start_proposal))
app.add_handler(CommandHandler("reset", reset_proposal))
app.add_handler(CommandHandler("resetdaily", reset_daily))
app.add_handler(CommandHandler("resetall", reset_all))

# Message handlers (order matters - specific before general)
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.VOICE, handle_audio))
app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# Run the bot
if __name__ == "__main__":
    import sys

    logger.info("🚀 Starting Tekne Admin Bot...")

    try:
        # run_polling() handles KeyboardInterrupt gracefully internally
        app.run_polling()
    except Exception as e:
        # Only catch unexpected fatal errors (not KeyboardInterrupt)
        logger.critical(f"💥 FATAL ERROR: {e}", exc_info=True)
        logger.critical("Bot will exit and restart (if configured)")
        sys.exit(1)  # Exit code 1 triggers Docker restart

    # If we reach here, it's a clean shutdown (Ctrl+C or normal stop)
    logger.info("👋 Bot stopped gracefully")
    sys.exit(0)
