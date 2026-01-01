"""
Callback system for communication between bot and agent

Uses ThreadLocal + Session Dict for thread-safe, session-isolated callbacks.
This prevents race conditions when multiple users send messages simultaneously.

Design:
- Callbacks stored in dict keyed by session_id
- ThreadLocal tracks current session_id in executor threads
- Tools call send_status() without args (session auto-detected)
"""

import threading
from typing import Optional, Callable, Tuple

# Thread-local storage for current session_id
_thread_local = threading.local()

# Session-scoped callbacks: Dict[session_id, (status_callback, session_state_callback)]
_session_callbacks: dict[str, Tuple[Optional[Callable], Optional[Callable]]] = {}


def set_current_session(session_id: Optional[str]) -> None:
    """
    Set the current session ID for this thread

    Called by get_agent_response() to bind session context to executor thread.
    This allows tools to call send_status() without passing session_id.
    """
    _thread_local.session_id = session_id


def get_current_session() -> Optional[str]:
    """Get the current session ID from thread-local storage"""
    return getattr(_thread_local, 'session_id', None)


def set_status_callback(session_id: str, callback: Optional[Callable[[str], None]]) -> None:
    """
    Register status callback for a specific session

    Args:
        session_id: Session identifier (e.g., "user_123")
        callback: Function to call when send_status() is invoked
    """
    if session_id not in _session_callbacks:
        _session_callbacks[session_id] = (None, None)

    _session_callbacks[session_id] = (callback, _session_callbacks[session_id][1])


def send_status(message: str) -> None:
    """
    Send status message to user for current session

    Session is auto-detected from ThreadLocal (set by get_agent_response).
    Thread-safe: each session has isolated callback.
    """
    session_id = get_current_session()
    if session_id and session_id in _session_callbacks:
        callback = _session_callbacks[session_id][0]
        if callback:
            callback(message)


def set_session_state_callback(session_id: str, callback: Optional[Callable[[str, dict], None]]) -> None:
    """
    Register session state callback for a specific session

    Args:
        session_id: Session identifier
        callback: Function to call when update_session_state() is invoked
    """
    if session_id not in _session_callbacks:
        _session_callbacks[session_id] = (None, None)

    _session_callbacks[session_id] = (_session_callbacks[session_id][0], callback)


def update_session_state(session_id: str, state_updates: dict) -> None:
    """
    Update session state for current session

    Note: session_id is passed as argument (kept for backward compatibility)
    """
    if session_id and session_id in _session_callbacks:
        callback = _session_callbacks[session_id][1]
        if callback:
            callback(session_id, state_updates)


def clear_session_callbacks(session_id: str) -> None:
    """
    Clear callbacks for a session (cleanup after request completes)

    Args:
        session_id: Session to clean up
    """
    if session_id in _session_callbacks:
        del _session_callbacks[session_id]
