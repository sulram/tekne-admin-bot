import os
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load environment variables from .env file
load_dotenv()


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/hello - Greet the bot
/help - Show this help message
"""
    await update.message.reply_text(help_text)


async def post_init(application) -> None:
    """Set bot commands in Telegram UI"""
    commands = [
        BotCommand("hello", "Greet the bot"),
        BotCommand("help", "Show available commands"),
    ]
    await application.bot.set_my_commands(commands)


app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).post_init(post_init).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("help", help_command))

app.run_polling()