import os
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from proposal_agent import get_agent_response

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Store user sessions for proposal generation
user_sessions = {}


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/hello - Greet the bot
/help - Show this help message
/proposal - Start creating a new proposal
/reset - Reset current proposal conversation

You can also:
- Send voice messages or audio files, and I'll transcribe them for you!
- Send text messages to chat with the proposal generator
"""
    await update.message.reply_text(help_text)


async def start_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new proposal generation session"""
    user_id = update.effective_user.id
    session_id = f"user_{user_id}"

    # Reset session
    user_sessions[user_id] = {"session_id": session_id, "active": True}

    # Send initial message to agent
    initial_message = "Olá! Quero criar uma nova proposta."

    status_msg = await update.message.reply_text("🚀 Iniciando gerador de propostas...")

    try:
        response = get_agent_response(initial_message, session_id=session_id)
        await status_msg.edit_text(response)
    except Exception as e:
        await status_msg.edit_text(f"❌ Erro ao iniciar agente: {str(e)}")


async def reset_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset proposal generation session"""
    user_id = update.effective_user.id

    if user_id in user_sessions:
        del user_sessions[user_id]

    await update.message.reply_text("✅ Sessão resetada! Use /proposal para começar uma nova proposta.")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - route to proposal agent if session is active"""
    user_id = update.effective_user.id
    user_text = update.message.text

    # Check if user has an active proposal session
    if user_id in user_sessions and user_sessions[user_id].get("active"):
        session_id = user_sessions[user_id]["session_id"]

        status_msg = await update.message.reply_text("💭 Processando...")

        try:
            response = get_agent_response(user_text, session_id=session_id)
            await status_msg.edit_text(response)
        except Exception as e:
            await status_msg.edit_text(f"❌ Erro: {str(e)}")
    else:
        # No active session - suggest starting one
        await update.message.reply_text(
            "💡 Para criar uma proposta, use /proposal\n"
            "Para ajuda, use /help"
        )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files, transcribe and send to agent if session active"""
    user_id = update.effective_user.id

    try:
        # Send initial status message
        status_msg = await update.message.reply_text("🎧 Transcrevendo áudio...")

        # Get the audio file (works for both voice messages and audio files)
        if update.message.voice:
            audio_file = await update.message.voice.get_file()
        elif update.message.audio:
            audio_file = await update.message.audio.get_file()
        else:
            await status_msg.edit_text("❌ Nenhum áudio encontrado")
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

        # Check if user has active proposal session
        if user_id in user_sessions and user_sessions[user_id].get("active"):
            session_id = user_sessions[user_id]["session_id"]
            await status_msg.edit_text(f"📝 Transcrição:\n{transcription}\n\n💭 Processando...")

            try:
                response = get_agent_response(transcription, session_id=session_id)
                await status_msg.edit_text(response)
            except Exception as e:
                await status_msg.edit_text(f"❌ Erro: {str(e)}")
        else:
            # No active session - just show transcription
            await status_msg.edit_text(f"📝 Transcrição:\n\n{transcription}")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao transcrever: {str(e)}")


async def post_init(application) -> None:
    """Set bot commands in Telegram UI"""
    commands = [
        BotCommand("hello", "Saudar o bot"),
        BotCommand("help", "Mostrar comandos disponíveis"),
        BotCommand("proposal", "Criar nova proposta comercial"),
        BotCommand("reset", "Resetar conversa atual"),
    ]
    await application.bot.set_my_commands(commands)


app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).post_init(post_init).build()

# Command handlers
app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("proposal", start_proposal))
app.add_handler(CommandHandler("reset", reset_proposal))

# Message handlers (order matters - specific before general)
app.add_handler(MessageHandler(filters.VOICE, handle_audio))
app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

app.run_polling()