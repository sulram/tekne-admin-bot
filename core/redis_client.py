"""
Redis client singleton for bot
Provides connection pooling and graceful fallback
"""

import logging
from typing import Optional

from config import REDIS_URL

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[any] = None  # Use any instead of redis.Redis to avoid import
_redis_available = None  # None = not tried yet, True = connected, False = failed


def get_redis_client() -> Optional[any]:
    """
    Get Redis client singleton

    Returns:
        Redis client if available, None if connection failed
    """
    global _redis_client, _redis_available

    # Return cached client if available
    if _redis_client is not None:
        return _redis_client

    # If we already tried and failed, don't retry on every call
    if _redis_available is False:  # Explicitly False, not None (which means not tried)
        return None

    try:
        # Import redis only when needed
        import redis
        from redis.exceptions import RedisError, ConnectionError

        # Log connection attempt (hide password)
        safe_url = REDIS_URL.replace(REDIS_URL.split('@')[0].split(':')[-1], '****') if '@' in REDIS_URL else REDIS_URL
        logger.info(f"🔌 Attempting Redis connection: {safe_url}")

        # Create connection pool
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,  # Auto-decode to strings
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # Test connection
        _redis_client.ping()
        _redis_available = True

        logger.info(f"✅ Redis connected: {safe_url}")
        return _redis_client

    except ImportError:
        logger.warning("⚠️ Redis module not installed - running without persistence")
        _redis_available = False
        _redis_client = None
        return None
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {type(e).__name__}: {e}")
        _redis_available = False
        _redis_client = None
        return None


def is_redis_available() -> bool:
    """Check if Redis is available"""
    client = get_redis_client()
    if client is None:
        return False

    try:
        client.ping()
        return True
    except:
        return False


def close_redis():
    """Close Redis connection (called on shutdown)"""
    global _redis_client
    if _redis_client:
        try:
            _redis_client.close()
            logger.info("✅ Redis connection closed")
        except:
            pass
        finally:
            _redis_client = None
