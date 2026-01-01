"""
Shared utilities for message handlers
Contains common callback factories and processing logic
"""

import asyncio
import logging
import re
import threading
from pathlib import Path
from typing import Optional, Callable
from telegram import Update

from config import SUBMODULE_PATH
from bot.auth import is_user_allowed

logger = logging.getLogger(__name__)


async def check_auth(update: Update, handler_name: str = "handler") -> Optional[int]:
    """
    Check if user is authorized to use the bot

    Args:
        update: Telegram update object
        handler_name: Name of handler for logging (e.g., "photo", "cost command")

    Returns:
        user_id if authorized, None if not authorized (rejection message already sent)
    """
    user_id = update.effective_user.id

    if not is_user_allowed(user_id):
        logger.warning(f"Unauthorized {handler_name} from user {user_id}")
        await update.message.reply_text("❌ Você não tem permissão para usar este bot.")
        return None

    return user_id


def create_status_callback(
    update: Update,
    loop: asyncio.AbstractEventLoop,
    progress_task_ref: list,  # Mutable reference [task]
) -> Callable[[str], None]:
    """
    Create status callback that sends messages to user and handles PDF detection

    Args:
        update: Telegram update object
        loop: Event loop for thread-safe async calls
        progress_task_ref: List containing progress task (for cancellation)

    Returns:
        Callback function for status messages
    """
    pdf_generated = False
    pdf_path_detected = None

    async def send_pdf_now(pdf_path_str: str):
        """Send PDF immediately when detected"""
        try:
            pdf_full_path = Path(SUBMODULE_PATH) / pdf_path_str

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
        nonlocal pdf_generated, pdf_path_detected
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
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(send_pdf_now(pdf_path_detected))
                )

        # Cancel progress when status message arrives
        if progress_task_ref and progress_task_ref[0] and not progress_task_ref[0].done():
            logger.info("Cancelling progress task due to status callback")
            progress_task_ref[0].cancel()

        # Create async task to send message immediately - use call_soon_threadsafe
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(update.message.reply_text(message))
        )

    return status_callback


def create_session_state_callback(
    user_id: int,
    user_sessions: dict,
    user_sessions_lock: threading.Lock
) -> Callable[[str, dict], None]:
    """
    Create session state callback for updating user session

    Args:
        user_id: Telegram user ID
        user_sessions: Dict of user sessions
        user_sessions_lock: Lock for thread-safe access

    Returns:
        Callback function for session state updates
    """
    def session_state_callback(session_id_key: str, state_updates: dict):
        """Callback to update user session state - thread-safe"""
        # This runs in the agent's thread, use lock for thread safety
        with user_sessions_lock:
            if user_id in user_sessions:
                user_sessions[user_id].update(state_updates)
                logger.info(f"✅ Updated session state for user {user_id}: {state_updates}")

    return session_state_callback


async def process_with_progress(
    status_msg,
    processing_func: Callable,
    *args,
    on_success: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
) -> Optional[str]:
    """
    Execute processing function with progress indicator

    Args:
        status_msg: Message to show progress on
        processing_func: Function to execute (will be run in executor)
        *args: Arguments to pass to processing_func
        on_success: Optional callback on success
        on_error: Optional callback on error

    Returns:
        Response from processing_func or None on error
    """
    from bot.utils import show_progress
    from anthropic import APIConnectionError, APITimeoutError
    import httpcore

    progress_task = None

    try:
        # Start progress indicator
        logger.info("Starting progress indicator")
        progress_task = asyncio.create_task(show_progress(status_msg))

        # Run processing in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, processing_func, *args)

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
            await status_msg.delete()
        except Exception:
            pass

        if on_success:
            await on_success(response)

        return response

    except (httpcore.ConnectError, APIConnectionError, APITimeoutError) as e:
        logger.error(f"API connection error: {str(e)}")
        if progress_task and not progress_task.done():
            progress_task.cancel()
        try:
            await status_msg.delete()
        except Exception:
            pass

        if on_error:
            await on_error(e)
        else:
            raise

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        if progress_task and not progress_task.done():
            progress_task.cancel()
        try:
            await status_msg.edit_text(f"❌ Erro: {str(e)}")
        except Exception:
            pass

        if on_error:
            await on_error(e)
        else:
            raise

    return None


class AgentProcessor:
    """
    Context manager for agent processing with automatic cleanup

    Handles:
    - Callback registration and cleanup
    - Progress indicator lifecycle
    - Status message deletion
    - Thread-safe session management

    Usage:
        async with AgentProcessor(update, session_id, user_id, status_msg,
                                  user_sessions, user_sessions_lock) as processor:
            await processor.run(message)
    """

    def __init__(
        self,
        update,
        session_id: str,
        user_id: int,
        status_msg,
        user_sessions: dict,
        user_sessions_lock
    ):
        """
        Initialize agent processor

        Args:
            update: Telegram update object
            session_id: User session ID
            user_id: Telegram user ID
            status_msg: Status message to update/delete
            user_sessions: Dict of user sessions (shared state)
            user_sessions_lock: Lock for thread-safe session access
        """
        self.update = update
        self.session_id = session_id
        self.user_id = user_id
        self.status_msg = status_msg
        self.user_sessions = user_sessions
        self.user_sessions_lock = user_sessions_lock
        self.progress_task = None
        self._loop = None

    async def __aenter__(self):
        """Setup callbacks and progress indicator"""
        from bot.utils import show_progress
        from core.callbacks import set_status_callback, set_session_state_callback

        # Get event loop
        self._loop = asyncio.get_event_loop()

        # Mutable reference for callback
        progress_ref = [None]

        # Create callbacks using shared factories
        status_callback = create_status_callback(self.update, self._loop, progress_ref)
        session_state_callback = create_session_state_callback(
            self.user_id,
            self.user_sessions,
            self.user_sessions_lock
        )

        # Register callbacks
        set_status_callback(self.session_id, status_callback)
        set_session_state_callback(self.session_id, session_state_callback)

        # Start progress indicator
        logger.info("Starting progress indicator")
        self.progress_task = asyncio.create_task(show_progress(self.status_msg))
        progress_ref[0] = self.progress_task

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

        # Clear session callbacks
        clear_session_callbacks(self.session_id)

        # Give status messages time to be sent
        await asyncio.sleep(0.5)

        # Delete status message
        try:
            await self.status_msg.delete()
        except Exception:
            pass

        # Don't suppress exceptions
        return False

    async def run(self, message: str) -> None:
        """
        Process message with agent and send response

        Handles everything: agent processing, error handling, sending response

        Args:
            message: Message to send to agent
        """
        from agent.agent import get_agent_response
        from bot.utils import send_long_message
        import httpcore
        from anthropic import APIConnectionError, APITimeoutError

        try:
            logger.info(f"Sending to agent (session {self.session_id}): {message[:50]}...")

            # Run agent in thread pool to avoid blocking event loop
            response = await self._loop.run_in_executor(None, get_agent_response, message, self.session_id)

            logger.info(f"Agent response length: {len(response)} chars")

            # Send response (handles long messages)
            await send_long_message(self.update, response, status_msg=None)

        except (httpcore.ConnectError, APIConnectionError, APITimeoutError) as e:
            logger.error(f"API connection error for user {self.user_id}: {str(e)}")
            await self.update.message.reply_text("⚠️ Problema de conexão com a API. Por favor, tente novamente.")

        except Exception as e:
            logger.error(f"Error processing message for user {self.user_id}: {str(e)}", exc_info=True)
            await self.update.message.reply_text(f"❌ Erro: {str(e)}")
