"""
Callback system for communication between bot and agent
"""

from typing import Optional, Callable

# Global callback for sending status messages to user
_status_callback: Optional[Callable[[str], None]] = None

# Global callback for managing user session state
_session_state_callback: Optional[Callable[[str, dict], None]] = None


def set_status_callback(callback: Optional[Callable[[str], None]]) -> None:
    """Set callback function to send status updates to user"""
    global _status_callback
    _status_callback = callback


def send_status(message: str) -> None:
    """Send status message to user if callback is set"""
    if _status_callback:
        _status_callback(message)


def set_session_state_callback(callback: Optional[Callable[[str, dict], None]]) -> None:
    """Set callback function to update user session state"""
    global _session_state_callback
    _session_state_callback = callback


def update_session_state(session_id: str, state_updates: dict) -> None:
    """Update user session state if callback is set"""
    if _session_state_callback:
        _session_state_callback(session_id, state_updates)
