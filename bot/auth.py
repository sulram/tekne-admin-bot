"""
User authentication and access control
"""

import logging
from config import ALLOWED_USERS

logger = logging.getLogger(__name__)


def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot"""
    # If ALLOWED_USERS is empty, allow all users
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def log_access_attempt(user_id: int, username: str, allowed: bool) -> None:
    """Log access attempt for monitoring"""
    if allowed:
        logger.info(f"Access granted to user {user_id} ({username})")
    else:
        logger.warning(f"Unauthorized access attempt by user {user_id} ({username})")
