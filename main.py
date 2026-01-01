import os
import logging
import time
import asyncio
import threading
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from proposal_agent import get_agent_response, set_status_callback, set_session_state_callback, get_cost_stats, reset_cost_tracking, reset_agent_session
import httpcore
from anthropic import APIConnectionError, APITimeoutError

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
# Structure: {user_id: {session_id: str, active: bool, waiting_for_image: dict}}
user_sessions = {}
user_sessions_lock = threading.Lock()

# Load allowed users from environment
ALLOWED_USERS_ENV = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = set()
if ALLOWED_USERS_ENV:
    ALLOWED_USERS = {int(user_id.strip()) for user_id in ALLOWED_USERS_ENV.split(",") if user_id.strip()}
    logger.info(f"Access control enabled for {len(ALLOWED_USERS)} users: {ALLOWED_USERS}")
else:
    logger.warning("⚠️  ALLOWED_USERS not set - bot is open to all users!")


def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot"""
    # If ALLOWED_USERS is empty, allow all users
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f'Hello {user.first_name}!\n'
        f'Your user ID: `{user.id}`'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/hello - Greet the bot
/help - Show this help message
/cost - Show API usage statistics
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

    # Check if user is allowed
    if not is_user_allowed(user_id):
        logger.warning(f"Unauthorized access attempt by user {user_id} ({update.effective_user.username})")
        await update.message.reply_text("❌ Você não tem permissão para usar este bot.")
        return

    session_id = f"user_{user_id}"

    logger.info(f"User {user_id} ({update.effective_user.username}) started new proposal")

    # Reset session
    with user_sessions_lock:
        user_sessions[user_id] = {"session_id": session_id, "active": True}

    # Send initial message to agent
    initial_message = "Olá! Liste as 10 propostas mais recentes. O que você gostaria de fazer: criar uma nova proposta ou editar uma existente?"

    status_msg = await update.message.reply_text("🚀 Iniciando gerador de propostas...")

    try:
        logger.info(f"Sending to agent: {initial_message}")
        response = get_agent_response(initial_message, session_id=session_id)
        logger.info(f"Agent response length: {len(response)} chars")
        await status_msg.edit_text(response)
    except (httpcore.ConnectError, APIConnectionError, APITimeoutError) as e:
        logger.error(f"API connection error for user {user_id}: {str(e)}")
        await status_msg.edit_text("⚠️ Problema de conexão com a API. Por favor, tente novamente.")
    except Exception as e:
        logger.error(f"Error starting agent for user {user_id}: {str(e)}", exc_info=True)
        await status_msg.edit_text(f"❌ Erro ao iniciar agente: {str(e)}")


async def reset_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset proposal generation session and cost tracking for this user"""
    user_id = update.effective_user.id
    session_id = f"user_{user_id}"

    with user_sessions_lock:
        if user_id in user_sessions:
            del user_sessions[user_id]

    # Reset agent conversation history for this session
    reset_agent_session(session_id)

    # Reset cost tracking for this user's session
    reset_cost_tracking(scope="session", session_id=session_id)

    await update.message.reply_text("✅ Sessão e custos resetados! Use /proposal para começar uma nova proposta.")


async def cost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show API usage and cost statistics"""
    user_id = update.effective_user.id

    # Check if user is allowed
    if not is_user_allowed(user_id):
        logger.warning(f"Unauthorized cost command from user {user_id}")
        await update.message.reply_text("❌ Você não tem permissão para usar este bot.")
        return

    try:
        stats = get_cost_stats()
        total = stats['total']
        daily = stats['daily']
        sessions = stats['sessions']

        from datetime import datetime

        # Build response message
        message = "📊 *Estatísticas de Uso da API*\n"
        message += "=" * 35 + "\n\n"

        # Total
        message += f"💵 *TOTAL (all time)*\n"
        message += f"   Custo: `${total['cost']:.4f}`\n"
        total_tokens = total['input_tokens'] + total['output_tokens']
        message += f"   Tokens: `{total['input_tokens']:,}` in + `{total['output_tokens']:,}` out = `{total_tokens:,}`\n\n"

        # Today
        today = datetime.now().strftime('%Y-%m-%d')
        if today in daily:
            d = daily[today]
            message += f"📅 *HOJE* ({today})\n"
            message += f"   Custo: `${d['cost']:.4f}`\n"
            message += f"   Requisições: `{d['requests']}`\n"
            message += f"   Tokens: `{d['input_tokens']:,}` in + `{d['output_tokens']:,}` out\n\n"

        # Recent days
        if len(daily) > 1:
            message += f"📆 *ÚLTIMOS 7 DIAS*\n"
            for day in sorted(daily.keys(), reverse=True)[:7]:
                d = daily[day]
                message += f"   `{day}`: ${d['cost']:.4f} ({d['requests']} req)\n"
            message += "\n"

        # User's session
        session_id = f"user_{user_id}"
        if session_id in sessions:
            s = sessions[session_id]
            message += f"👤 *SUA SESSÃO*\n"
            message += f"   Custo: `${s['cost']:.4f}`\n"
            message += f"   Requisições: `{s['requests']}`\n"
            message += f"   Tokens: `{s['input_tokens']:,}` in + `{s['output_tokens']:,}` out\n\n"

        # Last update
        if stats['last_update']:
            last_update_str = stats['last_update'][:19]  # Remove microseconds
            message += f"🕐 Última atualização: `{last_update_str}`\n"

        message += "=" * 35

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error getting cost stats: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao obter estatísticas: {str(e)}")


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

    # Check if user is allowed
    if not is_user_allowed(user_id):
        logger.warning(f"Unauthorized message from user {user_id}")
        await update.message.reply_text("❌ Você não tem permissão para usar este bot.")
        return

    logger.info(f"User {user_id} sent text: {user_text[:100]}...")

    # Check if user has an active proposal session
    with user_sessions_lock:
        has_active_session = user_id in user_sessions and user_sessions[user_id].get("active")
        session_id = user_sessions[user_id]["session_id"] if has_active_session else None

    if has_active_session:

        status_msg = await update.message.reply_text("💭 Processando...")
        progress_task = None

        # Setup status callback for this user - send messages immediately
        pdf_generated = False  # Flag to track if PDF was generated
        pdf_path_detected = None  # Store PDF path when detected

        async def send_pdf_now(pdf_path_str: str):
            """Send PDF immediately when detected"""
            try:
                from pathlib import Path
                pdf_full_path = Path("submodules/tekne-proposals") / pdf_path_str

                if pdf_full_path.exists():
                    logger.info(f"📄 Sending PDF immediately: {pdf_full_path}")
                    with open(pdf_full_path, 'rb') as pdf_file:
                        await update.message.reply_document(
                            document=pdf_file,
                            filename=pdf_full_path.name,
                            caption=f"📄 {pdf_full_path.name}"
                        )
                    logger.info("✅ PDF sent successfully")
                else:
                    logger.warning(f"PDF not found: {pdf_full_path}")
            except Exception as e:
                logger.error(f"Error sending PDF immediately: {e}", exc_info=True)

        def status_callback(message: str):
            """Callback to send status messages in real-time"""
            nonlocal progress_task, pdf_generated, pdf_path_detected
            logger.info(f"Status callback received: {message}")

            # Check if PDF was generated and extract path
            if "PDF gerado" in message:
                pdf_generated = True
                logger.info("🎯 PDF generation detected - extracting path...")

                # Extract PDF path from message
                import re
                pdf_match = re.search(r'docs/[^\s)]+\.pdf', message)
                if pdf_match:
                    pdf_path_detected = pdf_match.group(0)
                    logger.info(f"📍 PDF path detected: {pdf_path_detected}")
                    # Send PDF immediately via async task
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(send_pdf_now(pdf_path_detected))
                    )

            # Cancel progress when status message arrives
            if progress_task and not progress_task.done():
                logger.info("Cancelling progress task due to status callback")
                progress_task.cancel()

            # Create async task to send message immediately - use call_soon_threadsafe
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(update.message.reply_text(message))
            )

        def session_state_callback(session_id_key: str, state_updates: dict):
            """Callback to update user session state - thread-safe"""
            # This runs in the agent's thread, use lock for thread safety
            with user_sessions_lock:
                if user_id in user_sessions:
                    user_sessions[user_id].update(state_updates)
                    logger.info(f"✅ Updated session state for user {user_id}: {state_updates}")

        set_status_callback(status_callback)
        set_session_state_callback(session_state_callback)

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

            # PDF already sent immediately via callback - no need to send again

        except (httpcore.ConnectError, APIConnectionError, APITimeoutError) as e:
            logger.error(f"API connection error for user {user_id}: {str(e)}")
            if progress_task and not progress_task.done():
                progress_task.cancel()
            try:
                await status_msg.delete()
            except Exception:
                pass
            await update.message.reply_text("⚠️ Problema de conexão com a API. Por favor, tente novamente.")
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
            set_session_state_callback(None)
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

    # Try to find PDF path in response (multiple patterns)
    pdf_match = re.search(r'docs/[^\s)]+\.pdf', agent_response)

    if not pdf_match:
        # Try finding any .pdf reference
        pdf_match = re.search(r'[^\s:]+\.pdf', agent_response)

    if pdf_match:
        pdf_relative_path = pdf_match.group(0)
        # Remove any trailing punctuation and backticks
        pdf_relative_path = pdf_relative_path.strip('`').rstrip('.,;:)')

        pdf_path = Path("submodules/tekne-proposals") / pdf_relative_path

        # If exact path doesn't exist, try to find PDF in the same directory
        if not pdf_path.exists():
            logger.info(f"Exact PDF path not found: {pdf_path}, searching directory...")
            pdf_dir = pdf_path.parent
            if pdf_dir.exists():
                # Find any PDF file in the directory (most recent)
                pdf_files = sorted(pdf_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
                if pdf_files:
                    pdf_path = pdf_files[0]
                    logger.info(f"Found PDF in directory: {pdf_path}")

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
        else:
            logger.warning(f"PDF path not found: {pdf_path}")
    else:
        logger.info("No PDF path found in agent response")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages - save to proposal directory if agent is waiting"""
    user_id = update.effective_user.id

    # Check if user is allowed
    if not is_user_allowed(user_id):
        logger.warning(f"Unauthorized photo from user {user_id}")
        await update.message.reply_text("❌ Você não tem permissão para usar este bot.")
        return

    # Check if user has active session and is waiting for image
    with user_sessions_lock:
        if user_id not in user_sessions or not user_sessions[user_id].get("active"):
            await update.message.reply_text("💡 Use /proposal primeiro para criar uma proposta.")
            return

        session = user_sessions[user_id]
        waiting_for_image = session.get("waiting_for_image")
        logger.info(f"🔍 Photo handler - Session state: active={session.get('active')}, waiting_for_image={waiting_for_image}")

    if not waiting_for_image:
        await update.message.reply_text(
            "📷 Recebi a imagem, mas não estou esperando uma imagem no momento.\n"
            "Por favor, diga ao agente que deseja adicionar uma imagem à proposta."
        )
        return

    try:
        # Get the largest photo
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()

        status_msg = await update.message.reply_text("📥 Baixando imagem...")

        # Get proposal directory from session
        proposal_dir = waiting_for_image.get("proposal_dir")
        if not proposal_dir:
            await status_msg.edit_text("❌ Erro: diretório da proposta não encontrado.")
            return

        # Generate filename
        import time
        timestamp = int(time.time())
        image_filename = f"imagem-usuario-{timestamp}.jpg"

        # Full path to save
        from pathlib import Path
        proposal_path = Path("submodules/tekne-proposals") / proposal_dir
        proposal_path.mkdir(parents=True, exist_ok=True)
        image_path = proposal_path / image_filename

        # Download the image
        await photo_file.download_to_drive(str(image_path))

        # Use only filename (relative to the YAML file's directory)
        relative_image_path = image_filename

        logger.info(f"Saved user image to: {proposal_dir}/{image_filename} (will use relative path: {relative_image_path})")

        # Store image info in session and clear waiting state
        with user_sessions_lock:
            session["received_image"] = {
                "path": relative_image_path,
                "position": waiting_for_image.get("position", "before_first_section")
            }
            session["waiting_for_image"] = None
            session_id = session["session_id"]

        await status_msg.edit_text(
            f"✅ Imagem recebida e salva!\n"
            f"Agora vou adicionar à proposta..."
        )

        # Notify agent that image was received
        notification = f"Usuário enviou a imagem. Caminho: {relative_image_path}. Por favor, adicione a imagem à proposta na posição solicitada."

        # Create processing message with spinner
        processing_msg = await update.message.reply_text("💭 Processando...")
        progress_task = None

        # Setup callbacks for agent processing
        loop = asyncio.get_event_loop()
        pdf_generated = False  # Flag to track if PDF was generated
        pdf_path_detected = None

        async def send_pdf_now(pdf_path_str: str):
            """Send PDF immediately when detected"""
            try:
                from pathlib import Path
                pdf_full_path = Path("submodules/tekne-proposals") / pdf_path_str

                if pdf_full_path.exists():
                    logger.info(f"📄 Sending PDF immediately: {pdf_full_path}")
                    with open(pdf_full_path, 'rb') as pdf_file:
                        await update.message.reply_document(
                            document=pdf_file,
                            filename=pdf_full_path.name,
                            caption=f"📄 {pdf_full_path.name}"
                        )
                    logger.info("✅ PDF sent successfully")
                else:
                    logger.warning(f"PDF not found: {pdf_full_path}")
            except Exception as e:
                logger.error(f"Error sending PDF immediately: {e}", exc_info=True)

        def status_callback(message: str):
            """Callback to send status messages in real-time"""
            nonlocal progress_task, pdf_generated, pdf_path_detected
            logger.info(f"Status callback received: {message}")

            # Check if PDF was generated and extract path
            if "PDF gerado" in message:
                pdf_generated = True
                logger.info("🎯 PDF generation detected - extracting path...")

                # Extract PDF path from message
                import re
                pdf_match = re.search(r'docs/[^\s)]+\.pdf', message)
                if pdf_match:
                    pdf_path_detected = pdf_match.group(0)
                    logger.info(f"📍 PDF path detected: {pdf_path_detected}")
                    # Send PDF immediately via async task
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(send_pdf_now(pdf_path_detected))
                    )

            if progress_task and not progress_task.done():
                progress_task.cancel()
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(update.message.reply_text(message))
            )

        def session_state_callback_for_image(_: str, state_updates: dict):
            """Callback to update user session state - thread-safe"""
            with user_sessions_lock:
                if user_id in user_sessions:
                    user_sessions[user_id].update(state_updates)
                    logger.info(f"✅ Updated session state for user {user_id}: {state_updates}")

        set_status_callback(status_callback)
        set_session_state_callback(session_state_callback_for_image)

        # Start progress indicator
        progress_task = asyncio.create_task(show_progress(processing_msg))

        try:
            # Run agent to process the image
            response = await loop.run_in_executor(None, get_agent_response, notification, session_id)

            # Cancel progress indicator
            if progress_task and not progress_task.done():
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass

            # Give status messages time to be sent
            await asyncio.sleep(0.5)

            # Delete the progress message
            try:
                await processing_msg.delete()
            except Exception:
                pass

            await send_long_message(update, response, status_msg=None)

            # PDF already sent immediately via callback - no need to send again
        except Exception as e:
            logger.error(f"Error processing image with agent: {str(e)}", exc_info=True)
            if progress_task and not progress_task.done():
                progress_task.cancel()
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await update.message.reply_text(f"❌ Erro ao processar: {str(e)}")
        finally:
            # Clear callbacks
            set_status_callback(None)
            set_session_state_callback(None)

    except Exception as e:
        logger.error(f"Error handling photo: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao processar imagem: {str(e)}")


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files, transcribe and send to agent if session active"""
    user_id = update.effective_user.id

    # Check if user is allowed
    if not is_user_allowed(user_id):
        logger.warning(f"Unauthorized audio from user {user_id}")
        await update.message.reply_text("❌ Você não tem permissão para usar este bot.")
        return

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
        with user_sessions_lock:
            has_active_session = user_id in user_sessions and user_sessions[user_id].get("active")
            session_id = user_sessions[user_id]["session_id"] if has_active_session else None

        if has_active_session:
            # Show transcription in separate message to preserve it
            await status_msg.edit_text(f"📝 Transcrição:\n{transcription}")

            # Create new status message for processing
            processing_msg = await update.message.reply_text("💭 Processando...")
            progress_task = None

            # Setup status callback for this user - send messages immediately
            loop = asyncio.get_event_loop()
            pdf_generated = False  # Flag to track if PDF was generated
            pdf_path_detected = None

            async def send_pdf_now(pdf_path_str: str):
                """Send PDF immediately when detected"""
                try:
                    from pathlib import Path
                    pdf_full_path = Path("submodules/tekne-proposals") / pdf_path_str

                    if pdf_full_path.exists():
                        logger.info(f"📄 Sending PDF immediately: {pdf_full_path}")
                        with open(pdf_full_path, 'rb') as pdf_file:
                            await update.message.reply_document(
                                document=pdf_file,
                                filename=pdf_full_path.name,
                                caption=f"📄 {pdf_full_path.name}"
                            )
                        logger.info("✅ PDF sent successfully")
                    else:
                        logger.warning(f"PDF not found: {pdf_full_path}")
                except Exception as e:
                    logger.error(f"Error sending PDF immediately: {e}", exc_info=True)

            def status_callback(message: str):
                """Callback to send status messages in real-time"""
                nonlocal progress_task, pdf_generated, pdf_path_detected

                # Check if PDF was generated and extract path
                if "PDF gerado" in message:
                    pdf_generated = True
                    logger.info("🎯 PDF generation detected - extracting path...")

                    # Extract PDF path from message
                    import re
                    pdf_match = re.search(r'docs/[^\s)]+\.pdf', message)
                    if pdf_match:
                        pdf_path_detected = pdf_match.group(0)
                        logger.info(f"📍 PDF path detected: {pdf_path_detected}")
                        # Send PDF immediately via async task
                        loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(send_pdf_now(pdf_path_detected))
                        )

                # Cancel progress when status message arrives
                if progress_task and not progress_task.done():
                    progress_task.cancel()
                # Create async task to send message immediately - use call_soon_threadsafe
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(update.message.reply_text(message))
                )

            def session_state_callback(session_id_key: str, state_updates: dict):
                """Callback to update user session state - thread-safe"""
                # This runs in the agent's thread, use lock for thread safety
                with user_sessions_lock:
                    if user_id in user_sessions:
                        user_sessions[user_id].update(state_updates)
                        logger.info(f"✅ Updated session state for user {user_id}: {state_updates}")

            set_status_callback(status_callback)
            set_session_state_callback(session_state_callback)

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

                # PDF already sent immediately via callback - no need to send again

            except (httpcore.ConnectError, APIConnectionError, APITimeoutError) as e:
                logger.error(f"API connection error for user {user_id}: {str(e)}")
                if progress_task and not progress_task.done():
                    progress_task.cancel()
                try:
                    await processing_msg.delete()
                except Exception:
                    pass
                await update.message.reply_text("⚠️ Problema de conexão com a API. Por favor, tente novamente.")
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
                set_session_state_callback(None)
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
        BotCommand("cost", "Mostrar estatísticas de uso da API"),
        BotCommand("proposal", "Criar nova proposta comercial"),
        BotCommand("reset", "Resetar conversa e custos da sessão"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("✅ Bot commands set successfully")
    except Exception as e:
        logger.warning(f"⚠️  Could not set bot commands (will retry later): {str(e)}")
        # Don't fail startup - commands will still work, just won't show in UI


app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).post_init(post_init).build()

# Command handlers
app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("cost", cost_command))
app.add_handler(CommandHandler("proposal", start_proposal))
app.add_handler(CommandHandler("reset", reset_proposal))

# Message handlers (order matters - specific before general)
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.VOICE, handle_audio))
app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

app.run_polling()