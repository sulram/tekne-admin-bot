"""
User authentication and access control
"""

import logging
from typing import Optional
from config import ALLOWED_USERS

logger = logging.getLogger(__name__)


def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot"""
    # If ALLOWED_USERS is empty, allow all users
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


async def check_auth(update, handler_name: str = "handler") -> Optional[int]:
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


def log_access_attempt(user_id: int, username: str, allowed: bool) -> None:
    """Log access attempt for monitoring"""
    if allowed:
        logger.info(f"Access granted to user {user_id} ({username})")
    else:
        logger.warning(f"Unauthorized access attempt by user {user_id} ({username})")
