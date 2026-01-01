"""
User session management

Centralized session state for user conversations with the bot.
Thread-safe access to session data.
"""

import threading
from typing import Optional

# Store user sessions (user_id -> session_data)
user_sessions = {}
user_sessions_lock = threading.Lock()


def get_session_info(user_id: int) -> tuple[bool, Optional[str]]:
    """
    Get user session info in thread-safe manner

    Args:
        user_id: Telegram user ID

    Returns:
        (has_active_session, session_id)
    """
    with user_sessions_lock:
        has_active_session = user_id in user_sessions and user_sessions[user_id].get("active")
        session_id = user_sessions[user_id]["session_id"] if has_active_session else None
    return has_active_session, session_id


def create_session(user_id: int, session_id: str) -> None:
    """
    Create or reset a user session

    Args:
        user_id: Telegram user ID
        session_id: Session identifier
    """
    with user_sessions_lock:
        user_sessions[user_id] = {"session_id": session_id, "active": True}


def clear_session(user_id: int) -> None:
    """
    Clear a user session

    Args:
        user_id: Telegram user ID
    """
    with user_sessions_lock:
        if user_id in user_sessions:
            del user_sessions[user_id]
