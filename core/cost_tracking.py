"""
Cost tracking for API usage - Redis only
All costs are stored in Redis with atomic operations for thread-safety
"""

import logging
from datetime import datetime
from typing import Optional

from core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Redis key prefixes
REDIS_PREFIX = "cost:"
REDIS_TOTAL_KEY = f"{REDIS_PREFIX}total"
REDIS_SESSION_PREFIX = f"{REDIS_PREFIX}session:"
REDIS_DAILY_PREFIX = f"{REDIS_PREFIX}daily:"
REDIS_LAST_UPDATE_KEY = f"{REDIS_PREFIX}last_update"


def track_cost(
    input_tokens: int,
    output_tokens: int,
    cost: float,
    session_id: str = "default",
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> dict:
    """Track API costs in Redis with atomic operations

    Args:
        input_tokens: Base input tokens (not cached)
        output_tokens: Output tokens
        cost: Total cost for this request
        session_id: Session identifier
        cache_read_tokens: Tokens read from cache (optional)
        cache_creation_tokens: Tokens written to cache (optional)

    Returns:
        dict with 'this_request', 'session', 'today', 'total' cost info
    """
    redis = get_redis_client()

    if redis is None:
        logger.error("❌ Redis unavailable - cannot track costs")
        return {
            "this_request": cost,
            "session": 0.0,
            "today": 0.0,
            "total": 0.0,
        }

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        session_key = f"{REDIS_SESSION_PREFIX}{session_id}"
        daily_key = f"{REDIS_DAILY_PREFIX}{today}"

        # Use pipeline for atomic operations
        pipe = redis.pipeline()

        # Increment totals (atomic)
        pipe.hincrbyfloat(REDIS_TOTAL_KEY, "cost", cost)
        pipe.hincrby(REDIS_TOTAL_KEY, "input_tokens", input_tokens)
        pipe.hincrby(REDIS_TOTAL_KEY, "output_tokens", output_tokens)
        pipe.hincrby(REDIS_TOTAL_KEY, "cache_read_tokens", cache_read_tokens)
        pipe.hincrby(REDIS_TOTAL_KEY, "cache_creation_tokens", cache_creation_tokens)

        # Increment session totals (atomic)
        pipe.hincrbyfloat(session_key, "cost", cost)
        pipe.hincrby(session_key, "input_tokens", input_tokens)
        pipe.hincrby(session_key, "output_tokens", output_tokens)
        pipe.hincrby(session_key, "cache_read_tokens", cache_read_tokens)
        pipe.hincrby(session_key, "cache_creation_tokens", cache_creation_tokens)
        pipe.hincrby(session_key, "requests", 1)

        # Increment daily totals (atomic)
        pipe.hincrbyfloat(daily_key, "cost", cost)
        pipe.hincrby(daily_key, "input_tokens", input_tokens)
        pipe.hincrby(daily_key, "output_tokens", output_tokens)
        pipe.hincrby(daily_key, "cache_read_tokens", cache_read_tokens)
        pipe.hincrby(daily_key, "cache_creation_tokens", cache_creation_tokens)
        pipe.hincrby(daily_key, "requests", 1)

        # Update last update timestamp
        pipe.set(REDIS_LAST_UPDATE_KEY, datetime.now().isoformat())

        # Execute all operations atomically
        pipe.execute()

        # Get current totals for return value
        total_cost = float(redis.hget(REDIS_TOTAL_KEY, "cost") or 0)
        session_cost = float(redis.hget(session_key, "cost") or 0)
        daily_cost = float(redis.hget(daily_key, "cost") or 0)

        # Log with cache info if available
        cache_info = ""
        if cache_read_tokens > 0 or cache_creation_tokens > 0:
            cache_info = f" | Cache: {cache_read_tokens:,} read + {cache_creation_tokens:,} write"

        logger.info(
            f"📊 Session {session_id}: ${cost:.4f}{cache_info} | "
            f"Today: ${daily_cost:.4f} | Total: ${total_cost:.4f}"
        )

        return {
            "this_request": cost,
            "session": session_cost,
            "today": daily_cost,
            "total": total_cost,
        }

    except Exception as e:
        logger.error(f"❌ Redis error tracking cost: {e}")
        return {
            "this_request": cost,
            "session": 0.0,
            "today": 0.0,
            "total": 0.0,
        }


def get_cost_stats() -> dict:
    """Get cost statistics from Redis"""
    redis = get_redis_client()

    if redis is None:
        logger.error("❌ Redis unavailable - cannot get cost stats")
        return {
            "total": {"cost": 0.0, "input_tokens": 0, "output_tokens": 0},
            "sessions": {},
            "daily": {},
            "last_update": None,
        }

    try:
        # Get all total stats
        total_data = redis.hgetall(REDIS_TOTAL_KEY)
        total = {
            "cost": float(total_data.get("cost", 0)),
            "input_tokens": int(total_data.get("input_tokens", 0)),
            "output_tokens": int(total_data.get("output_tokens", 0)),
            "cache_read_tokens": int(total_data.get("cache_read_tokens", 0)),
            "cache_creation_tokens": int(total_data.get("cache_creation_tokens", 0)),
        }

        # Get all session stats
        sessions = {}
        for key in redis.scan_iter(f"{REDIS_SESSION_PREFIX}*"):
            session_id = key.replace(REDIS_SESSION_PREFIX, "")
            session_data = redis.hgetall(key)
            sessions[session_id] = {
                "cost": float(session_data.get("cost", 0)),
                "input_tokens": int(session_data.get("input_tokens", 0)),
                "output_tokens": int(session_data.get("output_tokens", 0)),
                "cache_read_tokens": int(session_data.get("cache_read_tokens", 0)),
                "cache_creation_tokens": int(session_data.get("cache_creation_tokens", 0)),
                "requests": int(session_data.get("requests", 0)),
            }

        # Get all daily stats
        daily = {}
        for key in redis.scan_iter(f"{REDIS_DAILY_PREFIX}*"):
            date = key.replace(REDIS_DAILY_PREFIX, "")
            daily_data = redis.hgetall(key)
            daily[date] = {
                "cost": float(daily_data.get("cost", 0)),
                "input_tokens": int(daily_data.get("input_tokens", 0)),
                "output_tokens": int(daily_data.get("output_tokens", 0)),
                "cache_read_tokens": int(daily_data.get("cache_read_tokens", 0)),
                "cache_creation_tokens": int(daily_data.get("cache_creation_tokens", 0)),
                "requests": int(daily_data.get("requests", 0)),
            }

        # Get last update
        last_update = redis.get(REDIS_LAST_UPDATE_KEY)

        return {
            "total": total,
            "sessions": sessions,
            "daily": daily,
            "last_update": last_update,
        }

    except Exception as e:
        logger.error(f"❌ Redis error getting stats: {e}")
        return {
            "total": {"cost": 0.0, "input_tokens": 0, "output_tokens": 0},
            "sessions": {},
            "daily": {},
            "last_update": None,
        }


def reset_cost_tracking(scope: str = "all", session_id: Optional[str] = None) -> None:
    """Reset cost tracking in Redis

    Args:
        scope: What to reset - "all", "daily", "sessions", or "session"
        session_id: Specific session ID to reset (when scope="session")
    """
    redis = get_redis_client()

    if redis is None:
        logger.error("❌ Redis unavailable - cannot reset cost tracking")
        return

    try:
        if scope == "all":
            # Delete all cost-related keys
            for key in redis.scan_iter(f"{REDIS_PREFIX}*"):
                redis.delete(key)
            logger.info("✅ All cost tracking data reset")

        elif scope == "session" and session_id:
            # Delete specific session
            session_key = f"{REDIS_SESSION_PREFIX}{session_id}"
            redis.delete(session_key)
            logger.info(f"✅ Session {session_id} cost tracking reset")

        elif scope == "daily":
            # Delete all daily stats
            for key in redis.scan_iter(f"{REDIS_DAILY_PREFIX}*"):
                redis.delete(key)
            logger.info("✅ Daily cost tracking reset")

        elif scope == "sessions":
            # Delete all session stats
            for key in redis.scan_iter(f"{REDIS_SESSION_PREFIX}*"):
                redis.delete(key)
            logger.info("✅ Session cost tracking reset")

    except Exception as e:
        logger.error(f"❌ Redis error resetting cost tracking: {e}")
