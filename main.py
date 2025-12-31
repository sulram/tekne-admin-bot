import os
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/hello - Greet the bot
/help - Show this help message

You can also send voice messages or audio files, and I'll transcribe them for you!
"""
    await update.message.reply_text(help_text)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files, transcribe them with OpenAI Whisper"""
    try:
        # Send initial status message
        status_msg = await update.message.reply_text("🎧 Received audio! Transcribing...")

        # Get the audio file (works for both voice messages and audio files)
        if update.message.voice:
            audio_file = await update.message.voice.get_file()
        elif update.message.audio:
            audio_file = await update.message.audio.get_file()
        else:
            await status_msg.edit_text("❌ No audio found in message")
            return

        # Download the audio file
        file_path = f"/tmp/{audio_file.file_id}.ogg"
        await audio_file.download_to_drive(file_path)

        # Transcribe with OpenAI Whisper
        with open(file_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                response_format="text"
            )

        # Clean up the temporary file
        os.remove(file_path)

        # Send the transcription
        await status_msg.edit_text(f"📝 Transcription:\n\n{transcription}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error transcribing audio: {str(e)}")


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

# Add handlers for voice messages and audio files
app.add_handler(MessageHandler(filters.VOICE, handle_audio))
app.add_handler(MessageHandler(filters.AUDIO, handle_audio))

app.run_polling()