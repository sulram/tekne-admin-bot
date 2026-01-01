"""
Configuration and constants for Tekne Admin Bot
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent
SUBMODULE_PATH = PROJECT_ROOT / "submodules" / "tekne-proposals"
DOCS_PATH = SUBMODULE_PATH / "docs"
CLAUDE_MD_PATH = SUBMODULE_PATH / "CLAUDE.md"
COST_TRACKING_FILE = PROJECT_ROOT / ".cost_tracking.txt"

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Access Control
ALLOWED_USERS_ENV = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = set()
if ALLOWED_USERS_ENV:
    ALLOWED_USERS = {int(user_id.strip()) for user_id in ALLOWED_USERS_ENV.split(",") if user_id.strip()}

# Telegram
MAX_MESSAGE_LENGTH = 4096

# Claude Pricing (Sonnet 4.5, as of Dec 2024)
CLAUDE_INPUT_PRICE_PER_1M = 3.00  # USD per 1M tokens
CLAUDE_OUTPUT_PRICE_PER_1M = 15.00  # USD per 1M tokens
