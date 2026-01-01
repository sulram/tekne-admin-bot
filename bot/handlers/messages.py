"""
Message handlers for text, audio, photo, and proposal messages
"""

import os
import logging
import time
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from openai import OpenAI

from config import OPENAI_API_KEY, SUBMODULE_PATH
from bot.auth import check_auth
from bot.agent_processor import AgentProcessor
from bot.session import create_session, user_sessions, user_sessions_lock

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================================
# PROPOSAL HANDLER
# ============================================================================

async def start_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new proposal generation session"""
    user_id = await check_auth(update, "proposal command")
    if user_id is None:
        return

    session_id = f"user_{user_id}"

    logger.info(f"User {user_id} ({update.effective_user.username}) started new proposal")

    # Create/reset session
    create_session(user_id, session_id)

    # Send initial message to agent
    initial_message = "Olá! Liste as 10 propostas mais recentes. O que você gostaria de fazer: criar uma nova proposta ou editar uma existente?"

    async with AgentProcessor(update, user_id) as processor:
        await processor.process(initial_message, status_text="🚀 Iniciando gerador de propostas...")


# ============================================================================
# TEXT MESSAGE HANDLER
# ============================================================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - route to proposal agent if session is active"""
    user_id = await check_auth(update, "text message")
    if user_id is None:
        return

    user_text = update.message.text

    logger.info(f"User {user_id} sent text: {user_text[:100]}...")

    # Process with agent (validates session internally)
    async with AgentProcessor(update, user_id) as processor:
        await processor.process(user_text)


# ============================================================================
# AUDIO HANDLER
# ============================================================================

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files, transcribe and send to agent if session active"""
    user_id = await check_auth(update, "audio message")
    if user_id is None:
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

        # Show transcription
        await status_msg.edit_text(f"📝 Transcrição:\n{transcription}")

        # Process with agent (validates session internally)
        async with AgentProcessor(update, user_id) as processor:
            await processor.process(transcription)

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao transcrever: {str(e)}")


# ============================================================================
# PHOTO HANDLER
# ============================================================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages - save to proposal directory if agent is waiting"""
    user_id = await check_auth(update, "photo message")
    if user_id is None:
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
        timestamp = int(time.time())
        image_filename = f"imagem-usuario-{timestamp}.jpg"

        # Full path to save
        proposal_path = Path(SUBMODULE_PATH) / proposal_dir
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

        # Process with agent
        async with AgentProcessor(update, user_id) as processor:
            await processor.process(notification)

    except Exception as e:
        logger.error(f"Error handling photo: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao processar imagem: {str(e)}")
