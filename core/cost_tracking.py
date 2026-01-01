"""
Cost tracking for API usage
"""

import json
import logging
from datetime import datetime
from config import COST_TRACKING_FILE

logger = logging.getLogger(__name__)


def track_cost(input_tokens: int, output_tokens: int, cost: float, session_id: str = "default") -> dict:
    """Track API costs to a file for monitoring

    Returns:
        dict with 'this_request', 'session', 'today', 'total' cost info
    """
    try:
        # Read existing data
        data = {
            'total': {'cost': 0.0, 'input_tokens': 0, 'output_tokens': 0},
            'sessions': {},
            'daily': {},
            'last_update': None
        }

        if COST_TRACKING_FILE.exists():
            try:
                with open(COST_TRACKING_FILE, 'r') as f:
                    data = json.load(f)
            except:
                pass  # If file is corrupted, start fresh

        # Update totals
        data['total']['cost'] += cost
        data['total']['input_tokens'] += input_tokens
        data['total']['output_tokens'] += output_tokens

        # Update session totals
        if session_id not in data['sessions']:
            data['sessions'][session_id] = {'cost': 0.0, 'input_tokens': 0, 'output_tokens': 0, 'requests': 0}
        data['sessions'][session_id]['cost'] += cost
        data['sessions'][session_id]['input_tokens'] += input_tokens
        data['sessions'][session_id]['output_tokens'] += output_tokens
        data['sessions'][session_id]['requests'] += 1

        # Update daily totals
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in data['daily']:
            data['daily'][today] = {'cost': 0.0, 'input_tokens': 0, 'output_tokens': 0, 'requests': 0}
        data['daily'][today]['cost'] += cost
        data['daily'][today]['input_tokens'] += input_tokens
        data['daily'][today]['output_tokens'] += output_tokens
        data['daily'][today]['requests'] += 1

        data['last_update'] = datetime.now().isoformat()

        # Write updated data
        with open(COST_TRACKING_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"📊 Session {session_id}: ${cost:.4f} | Today: ${data['daily'][today]['cost']:.4f} | Total: ${data['total']['cost']:.4f}")

        # Return cost info for display
        return {
            'this_request': cost,
            'session': data['sessions'][session_id]['cost'],
            'today': data['daily'][today]['cost'],
            'total': data['total']['cost']
        }
    except Exception as e:
        logger.warning(f"Could not track cost: {e}")
        return {
            'this_request': cost,
            'session': 0.0,
            'today': 0.0,
            'total': 0.0
        }


def get_cost_stats() -> dict:
    """Get cost statistics"""
    if not COST_TRACKING_FILE.exists():
        return {
            'total': {'cost': 0.0, 'input_tokens': 0, 'output_tokens': 0},
            'sessions': {},
            'daily': {},
            'last_update': None
        }

    try:
        with open(COST_TRACKING_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading cost tracking: {e}")
        return {
            'total': {'cost': 0.0, 'input_tokens': 0, 'output_tokens': 0},
            'sessions': {},
            'daily': {},
            'last_update': None
        }


def reset_cost_tracking(scope: str = "all", session_id: str = None) -> None:
    """Reset cost tracking

    Args:
        scope: What to reset - "all", "daily", "sessions", or "session"
        session_id: Specific session ID to reset (when scope="session")
    """
    if scope == "all":
        # Delete the file completely
        if COST_TRACKING_FILE.exists():
            COST_TRACKING_FILE.unlink()
        logger.info("✅ All cost tracking data reset")
    elif scope == "session" and session_id:
        # Reset only a specific session
        data = get_cost_stats()
        if session_id in data['sessions']:
            del data['sessions'][session_id]
            logger.info(f"✅ Session {session_id} cost tracking reset")
            with open(COST_TRACKING_FILE, 'w') as f:
                json.dump(data, f, indent=2)
    else:
        data = get_cost_stats()

        if scope == "daily":
            data['daily'] = {}
            logger.info("✅ Daily cost tracking reset")
        elif scope == "sessions":
            data['sessions'] = {}
            logger.info("✅ Session cost tracking reset")

        with open(COST_TRACKING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
