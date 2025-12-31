import os
import logging
import time
import asyncio
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from proposal_agent import get_agent_response, set_status_callback

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suppress httpx INFO logs to avoid flooding
logging.getLogger("httpx").setLevel(logging.WARNING)

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

    logger.info(f"User {user_id} ({update.effective_user.username}) started new proposal")

    # Reset session
    user_sessions[user_id] = {"session_id": session_id, "active": True}

    # Send initial message to agent
    initial_message = "Olá! Quero criar uma nova proposta."

    status_msg = await update.message.reply_text("🚀 Iniciando gerador de propostas...")

    try:
        logger.info(f"Sending to agent: {initial_message}")
        response = get_agent_response(initial_message, session_id=session_id)
        logger.info(f"Agent response length: {len(response)} chars")
        await status_msg.edit_text(response)
    except Exception as e:
        logger.error(f"Error starting agent for user {user_id}: {str(e)}", exc_info=True)
        await status_msg.edit_text(f"❌ Erro ao iniciar agente: {str(e)}")


async def reset_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset proposal generation session"""
    user_id = update.effective_user.id

    if user_id in user_sessions:
        del user_sessions[user_id]

    await update.message.reply_text("✅ Sessão resetada! Use /proposal para começar uma nova proposta.")


async def show_progress(status_msg) -> None:
    """Show animated progress indicator while agent is processing"""
    spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    messages = [
        "💭 Processando",
        "🤔 Analisando sua solicitação",
        "📝 Preparando resposta",
        "🧠 Pensando",
        "⚙️ Trabalhando nisso",
    ]

    spinner_idx = 0
    message_idx = 0
    elapsed = 0

    try:
        while True:
            # Update message every 3 seconds, spinner every 0.3s
            if elapsed % 10 == 0:  # Every 3 seconds
                current_message = messages[message_idx % len(messages)]
                message_idx += 1

            spinner = spinners[spinner_idx % len(spinners)]

            try:
                await status_msg.edit_text(f"{spinner} {current_message}...")
            except Exception:
                # Ignore errors if message hasn't changed or rate limited
                pass

            await asyncio.sleep(0.3)
            spinner_idx += 1
            elapsed += 1

    except asyncio.CancelledError:
        # Task was cancelled, processing is done
        pass


async def send_long_message(update: Update, message: str, status_msg=None) -> None:
    """Send long messages by splitting them into chunks"""
    MAX_LENGTH = 4096

    if len(message) <= MAX_LENGTH:
        if status_msg:
            await status_msg.edit_text(message)
        else:
            await update.message.reply_text(message)
        return

    # Delete status message if exists
    if status_msg:
        await status_msg.delete()

    # Split message into chunks
    chunks = []
    while message:
        if len(message) <= MAX_LENGTH:
            chunks.append(message)
            break

        # Find a good break point (newline, period, or space)
        split_at = MAX_LENGTH
        for sep in ['\n\n', '\n', '. ', ' ']:
            pos = message[:MAX_LENGTH].rfind(sep)
            if pos > MAX_LENGTH * 0.7:  # Don't split too early
                split_at = pos + len(sep)
                break

        chunks.append(message[:split_at])
        message = message[split_at:]

    # Send chunks
    for i, chunk in enumerate(chunks):
        if i == 0:
            await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(f"(continuação {i+1}):\n\n{chunk}")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - route to proposal agent if session is active"""
    user_id = update.effective_user.id
    user_text = update.message.text

    logger.info(f"User {user_id} sent text: {user_text[:100]}...")

    # Check if user has an active proposal session
    if user_id in user_sessions and user_sessions[user_id].get("active"):
        session_id = user_sessions[user_id]["session_id"]

        status_msg = await update.message.reply_text("💭 Processando...")
        progress_task = None

        # Setup status callback for this user - send messages immediately
        def status_callback(message: str):
            """Callback to send status messages in real-time"""
            nonlocal progress_task
            logger.info(f"Status callback received: {message}")
            # Cancel progress when status message arrives
            if progress_task and not progress_task.done():
                logger.info("Cancelling progress task due to status callback")
                progress_task.cancel()
            # Create async task to send message immediately - use call_soon_threadsafe
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(update.message.reply_text(message))
            )

        set_status_callback(status_callback)

        # Start progress indicator task
        logger.info("Starting progress indicator")
        progress_task = asyncio.create_task(show_progress(status_msg))

        try:
            logger.info(f"Sending to agent (session {session_id}): {user_text[:50]}...")
            # Run agent in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, get_agent_response, user_text, session_id)
            logger.info(f"Agent response length: {len(response)} chars")

            # Cancel progress indicator
            if progress_task and not progress_task.done():
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass

            # Give status messages time to be sent
            await asyncio.sleep(0.5)

            # Delete the progress message before sending final response
            try:
                await status_msg.delete()
            except Exception:
                pass

            # Send response (handles long messages)
            await send_long_message(update, response, status_msg=None)

            # Check for PDF file mentioned in response
            if "PDF gerado" in response or ".pdf" in response:
                await send_pdf_if_exists(update, response)

        except Exception as e:
            logger.error(f"Error processing message for user {user_id}: {str(e)}", exc_info=True)
            if progress_task and not progress_task.done():
                progress_task.cancel()
            if status_msg:
                try:
                    await status_msg.edit_text(f"❌ Erro: {str(e)}")
                except Exception:
                    await update.message.reply_text(f"❌ Erro: {str(e)}")
            else:
                await update.message.reply_text(f"❌ Erro: {str(e)}")
        finally:
            # Clear status callback
            set_status_callback(None)
    else:
        # No active session - suggest starting one
        await update.message.reply_text(
            "💡 Para criar uma proposta, use /proposal\n"
            "Para ajuda, use /help"
        )


async def send_pdf_if_exists(update: Update, agent_response: str) -> None:
    """Extract PDF path from agent response and send if exists"""
    import re
    from pathlib import Path

    # Try to find PDF path in response
    pdf_match = re.search(r'docs/[^\s]+\.pdf', agent_response)
    if pdf_match:
        pdf_path = Path("submodules/tekne-proposals") / pdf_match.group(0)
        if pdf_path.exists():
            logger.info(f"Sending PDF: {pdf_path}")
            try:
                with open(pdf_path, 'rb') as pdf_file:
                    await update.message.reply_document(
                        document=pdf_file,
                        filename=pdf_path.name,
                        caption="📄 Proposta gerada!"
                    )
            except Exception as e:
                logger.error(f"Error sending PDF: {str(e)}")
                await update.message.reply_text(f"❌ Erro ao enviar PDF: {str(e)}")


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files, transcribe and send to agent if session active"""
    user_id = update.effective_user.id

    try:
        # Log audio reception
        audio_type = "voice" if update.message.voice else "audio"
        logger.info(f"User {user_id} sent {audio_type} message")

        # Send initial status message
        status_msg = await update.message.reply_text("🎧 Transcrevendo áudio...")

        # Get the audio file (works for both voice messages and audio files)
        if update.message.voice:
            audio_file = await update.message.voice.get_file()
            duration = update.message.voice.duration
            logger.info(f"Voice duration: {duration}s")
        elif update.message.audio:
            audio_file = await update.message.audio.get_file()
            duration = update.message.audio.duration if update.message.audio.duration else "unknown"
            logger.info(f"Audio duration: {duration}s")
        else:
            await status_msg.edit_text("❌ Nenhum áudio encontrado")
            return

        # Download the audio file
        file_path = f"/tmp/{audio_file.file_id}.ogg"
        await audio_file.download_to_drive(file_path)
        logger.info(f"Audio downloaded to: {file_path}")

        # Transcribe with OpenAI Whisper
        logger.info("Starting Whisper transcription...")
        start_time = time.time()

        with open(file_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                response_format="text"
            )

        elapsed_time = time.time() - start_time

        # Log transcription result
        logger.info(f"⏱️  Whisper API response time: {elapsed_time:.2f} seconds")
        logger.info(f"✅ Transcription complete ({len(transcription)} chars):")
        logger.info(f"   \"{transcription}\"")

        # Clean up the temporary file
        os.remove(file_path)

        # Check if user has active proposal session
        if user_id in user_sessions and user_sessions[user_id].get("active"):
            session_id = user_sessions[user_id]["session_id"]
            # Show transcription in separate message to preserve it
            await status_msg.edit_text(f"📝 Transcrição:\n{transcription}")

            # Create new status message for processing
            processing_msg = await update.message.reply_text("💭 Processando...")
            progress_task = None

            # Setup status callback for this user - send messages immediately
            loop = asyncio.get_event_loop()
            def status_callback(message: str):
                """Callback to send status messages in real-time"""
                nonlocal progress_task
                # Cancel progress when status message arrives
                if progress_task and not progress_task.done():
                    progress_task.cancel()
                # Create async task to send message immediately - use call_soon_threadsafe
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(update.message.reply_text(message))
                )

            set_status_callback(status_callback)

            # Start progress indicator task
            progress_task = asyncio.create_task(show_progress(processing_msg))

            try:
                # Run agent in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, get_agent_response, transcription, session_id)

                # Cancel progress indicator
                if progress_task and not progress_task.done():
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass

                # Give status messages time to be sent
                await asyncio.sleep(0.5)

                # Delete the progress message before sending final response
                try:
                    await processing_msg.delete()
                except Exception:
                    pass

                # Send response (handles long messages)
                await send_long_message(update, response, status_msg=None)

                # Check for PDF in response
                if "PDF gerado" in response or ".pdf" in response:
                    await send_pdf_if_exists(update, response)

            except Exception as e:
                logger.error(f"Error processing transcription: {str(e)}", exc_info=True)
                if progress_task and not progress_task.done():
                    progress_task.cancel()
                try:
                    await processing_msg.edit_text(f"❌ Erro: {str(e)}")
                except Exception:
                    await update.message.reply_text(f"❌ Erro: {str(e)}")
            finally:
                # Clear status callback
                set_status_callback(None)
        else:
            # No active session - just show transcription
            await status_msg.edit_text(f"📝 Transcrição:\n\n{transcription}")

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}", exc_info=True)
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