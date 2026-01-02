"""
Redis client singleton for bot
Provides connection pooling and graceful fallback
"""

import logging
import os
from typing import Optional
import redis
from redis.exceptions import RedisError, ConnectionError

from config import REDIS_URL

logger = logging.getLogger(__name__)

# DEBUG: Print REDIS_URL at module import (using print for visibility before logging is configured)
print(f"🔍🔍🔍 DEBUG redis_client.py: REDIS_URL from env = {os.getenv('REDIS_URL', 'NOT SET')}")
print(f"🔍🔍🔍 DEBUG redis_client.py: REDIS_URL from config = {REDIS_URL}")

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None
_redis_available = None  # None = not tried yet, True = connected, False = failed


def get_redis_client() -> Optional[redis.Redis]:
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
        # Log connection attempt (hide password)
        safe_url = REDIS_URL.replace(REDIS_URL.split('@')[0].split(':')[-1], '****') if '@' in REDIS_URL else REDIS_URL
        print(f"🔌🔌🔌 DEBUG: Attempting Redis connection to: {safe_url}")
        logger.info(f"🔌 Attempting Redis connection: {safe_url}")

        # Create connection pool
        print(f"🔌🔌🔌 DEBUG: Creating Redis client from URL...")
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,  # Auto-decode to strings
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # Test connection
        print(f"🔌🔌🔌 DEBUG: Testing connection with PING...")
        _redis_client.ping()
        _redis_available = True

        print(f"✅✅✅ DEBUG: Redis connected successfully!")
        logger.info(f"✅ Redis connected: {safe_url}")
        return _redis_client

    except (RedisError, ConnectionError) as e:
        print(f"❌❌❌ DEBUG: Redis connection failed: {type(e).__name__}: {e}")
        logger.error(f"❌ Redis connection failed: {type(e).__name__}: {e}")
        logger.error(f"   URL attempted: {safe_url}")
        _redis_available = False
        _redis_client = None
        return None
    except Exception as e:
        print(f"❌❌❌ DEBUG: Unexpected Redis error: {type(e).__name__}: {e}")
        logger.error(f"❌ Unexpected Redis error: {type(e).__name__}: {e}")
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
