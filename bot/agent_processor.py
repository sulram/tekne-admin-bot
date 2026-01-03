"""
AgentProcessor - Self-contained context manager for agent processing

Handles complete agent workflow with automatic cleanup:
- Session validation (auth + active session check)
- Callback registration and cleanup (ThreadLocal + Session Dict)
- Progress indicator lifecycle
- Agent execution in thread pool
- Response sending (long message handling)
- Comprehensive error handling (API + general)
- Status message deletion
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Callable, Optional

from config import SUBMODULE_PATH

logger = logging.getLogger(__name__)


class AgentProcessor:
    """
    Self-contained context manager for agent processing

    Handles everything from session validation to agent execution and cleanup.
    Handlers just need to call: async with AgentProcessor(update, user_id) as p: await p.process(msg)

    Usage:
        async with AgentProcessor(update, user_id) as processor:
            await processor.process(message, status_text="💭 Processando...")
    """

    def __init__(self, update, user_id: int):
        """
        Initialize agent processor

        Args:
            update: Telegram update object
            user_id: Telegram user ID (must be authorized)
        """
        self.update = update
        self.user_id = user_id
        self.session_id: Optional[str] = None
        self.status_msg = None
        self.progress_task = None
        self._loop = None
        self._has_session = False

    def _create_status_callback(self, progress_task_ref: list) -> Callable[[str], None]:
        """
        Create status callback for sending messages and handling PDF detection

        Args:
            progress_task_ref: Mutable reference to progress task

        Returns:
            Callback function for status messages
        """
        pdf_generated = False
        pdf_path_detected = None
        image_path_detected = None

        async def send_pdf_now(pdf_path_str: str):
            """Send PDF immediately when detected"""
            try:
                pdf_full_path = Path(SUBMODULE_PATH) / pdf_path_str

                if pdf_full_path.exists():
                    logger.info(f"📄 Sending PDF immediately: {pdf_full_path}")
                    with open(pdf_full_path, 'rb') as pdf_file:
                        await self.update.message.reply_document(
                            document=pdf_file,
                            filename=pdf_full_path.name,
                            caption=f"📄 {pdf_full_path.name}"
                        )
                    logger.info("✅ PDF sent successfully")
                else:
                    logger.warning(f"PDF not found: {pdf_full_path}")
            except Exception as e:
                logger.error(f"Error sending PDF immediately: {e}", exc_info=True)

        async def send_image_now(image_path_str: str):
            """Send image immediately when detected"""
            try:
                image_full_path = Path(SUBMODULE_PATH) / image_path_str

                if image_full_path.exists():
                    logger.info(f"🖼️ Sending image immediately: {image_full_path}")
                    with open(image_full_path, 'rb') as img_file:
                        await self.update.message.reply_photo(
                            photo=img_file,
                            caption=f"🎨 {image_full_path.name}"
                        )
                    logger.info("✅ Image sent successfully")
                else:
                    logger.warning(f"Image not found: {image_full_path}")
            except Exception as e:
                logger.error(f"Error sending image immediately: {e}", exc_info=True)

        def status_callback(message: str):
            """Callback to send status messages in real-time"""
            nonlocal pdf_generated, pdf_path_detected, image_path_detected
            logger.info(f"Status callback received: {message}")

            # Check if PDF was generated and extract path
            if "PDF gerado" in message:
                pdf_generated = True
                logger.info("🎯 PDF generation detected - extracting path...")

                # Extract PDF path from message
                pdf_match = re.search(r'docs/[^\s)]+\.pdf', message)
                if pdf_match:
                    pdf_path_detected = pdf_match.group(0)
                    logger.info(f"📍 PDF path detected: {pdf_path_detected}")
                    # Send PDF immediately via async task
                    self._loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(send_pdf_now(pdf_path_detected))
                    )

            # Check if image was generated and extract path
            if "Imagem gerada" in message:
                logger.info("🎯 Image generation detected - extracting path...")

                # Extract image path from message (docs/.../file.png)
                image_match = re.search(r'docs/[^\s)]+\.(?:png|jpg|jpeg)', message)
                if image_match:
                    image_path_detected = image_match.group(0)
                    logger.info(f"📍 Image path detected: {image_path_detected}")
                    # Send image immediately via async task
                    self._loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(send_image_now(image_path_detected))
                    )

            # Cancel progress when status message arrives
            if progress_task_ref and progress_task_ref[0] and not progress_task_ref[0].done():
                logger.info("Cancelling progress task due to status callback")
                progress_task_ref[0].cancel()

            # Create async task to send message immediately - use call_soon_threadsafe
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.update.message.reply_text(message))
            )

        return status_callback

    def _create_session_state_callback(self) -> Callable[[str, dict], None]:
        """
        Create session state callback for updating user session

        Returns:
            Callback function for session state updates
        """
        def session_state_callback(session_id_key: str, state_updates: dict):
            """Callback to update user session state - thread-safe"""
            from bot.session import user_sessions, user_sessions_lock

            # This runs in the agent's thread, use lock for thread safety
            with user_sessions_lock:
                if self.user_id in user_sessions:
                    user_sessions[self.user_id].update(state_updates)
                    logger.info(f"✅ Updated session state for user {self.user_id}: {state_updates}")

        return session_state_callback

    async def __aenter__(self):
        """Setup: validate session, create status message, register callbacks"""
        from bot.session import get_session_info

        # Get event loop
        self._loop = asyncio.get_event_loop()

        # Check if user has active session
        self._has_session, self.session_id = get_session_info(self.user_id)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup callbacks, progress, and status message"""
        from core.callbacks import clear_session_callbacks

        # Cancel progress indicator
        if self.progress_task and not self.progress_task.done():
            self.progress_task.cancel()
            try:
                await self.progress_task
            except asyncio.CancelledError:
                pass

        # Clear session callbacks (only if session was active)
        if self._has_session and self.session_id:
            clear_session_callbacks(self.session_id)

        # Give status messages time to be sent
        await asyncio.sleep(0.5)

        # Delete status message
        if self.status_msg:
            try:
                await self.status_msg.delete()
            except Exception:
                pass

        # Don't suppress exceptions
        return False

    async def process(self, message: str, status_text: str = "💭 Processando...") -> None:
        """
        Process message with agent (if session active)

        This is the main entry point. Handles:
        - Session validation
        - Status message creation
        - Callback setup
        - Team execution (CopyMaster + Reviewer)
        - Error handling

        Args:
            message: Message to send to agent
            status_text: Text to show in status message
        """
        from agent.team import run_team  # Use Team directly
        from bot.utils import send_long_message, show_progress
        from core.callbacks import set_status_callback, set_session_state_callback
        import httpcore
        from anthropic import APIConnectionError, APITimeoutError

        # Check if user has active session
        if not self._has_session:
            await self.update.message.reply_text(
                "💡 Para criar uma proposta, use /proposal\n"
                "Para ajuda, use /help"
            )
            return

        try:
            # Create status message (simple, no spinner)
            self.status_msg = await self.update.message.reply_text("💭 Processando...")

            # Mutable reference for callback
            progress_ref = [None]

            # Create callbacks using internal methods
            status_callback = self._create_status_callback(progress_ref)
            session_state_callback = self._create_session_state_callback()

            # Register callbacks
            set_status_callback(self.session_id, status_callback)
            set_session_state_callback(self.session_id, session_state_callback)

            # NO SPINNER - Telegram will be more responsive with reasoning messages
            # The status_callback will send real-time updates as they happen

            # Process with Team (CopyMaster + Reviewer)
            logger.info(f"🤖 [TEAM] Sending to team (session {self.session_id}): {message[:50]}...")
            # Run team in thread pool to avoid blocking event loop
            response = await self._loop.run_in_executor(None, run_team, message, self.session_id)

            logger.info(f"Agent response length: {len(response)} chars")

            # Send response (handles long messages)
            await send_long_message(self.update, response, status_msg=None)

        except (httpcore.ConnectError, APIConnectionError, APITimeoutError) as e:
            logger.error(f"API connection error for user {self.user_id}: {str(e)}")
            await self.update.message.reply_text("⚠️ Problema de conexão com a API. Por favor, tente novamente.")

        except Exception as e:
            logger.error(f"Error processing message for user {self.user_id}: {str(e)}", exc_info=True)
            await self.update.message.reply_text(f"❌ Erro: {str(e)}")
