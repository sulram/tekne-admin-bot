# tekne-admin-bot

AI-powered Telegram bot for generating and managing Tekne Studio proposals.

## Features

- AI proposal generation using Claude Sonnet 4.5 via [Agno](https://docs.agno.com)
- PDF export with Typst typesetting
- Git integration for version control
- Cost tracking with Redis persistence
- Prompt caching for 45% cost reduction

## Quick Start

### Local Development (Docker Compose - Recommended)

```bash
# Configure environment
cp .env.example .env
# Edit .env with your tokens

# Run with Docker Compose
docker compose up -d

# View logs
docker compose logs -f bot
```

### Alternative: Local Python

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -r requirements.txt

# Run
python main.py
```

### Environment Variables

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
ALLOWED_USERS=27463101  # Comma-separated Telegram user IDs

# Optional: for git push operations
GITHUB_TOKEN=your_github_token
```

## Production Deploy (Dokploy)

**Important:** Force Dokploy to use **Dockerfile** (not Nixpacks):
- Builder Type: `Dockerfile`
- Dockerfile Path: `./Dockerfile`

The Dockerfile includes Typst binary installation (required for PDF generation).

**Requirements:**
- GitHub token or GitHub App for private `tekne-proposals` submodule access
- Redis persistence via `redis-data` volume (auto-created)

### Redis Persistence

All data persists in Redis with AOF:
- Agent memory (conversations)
- Cost tracking (API usage)

```bash
# View costs
docker exec -it tekne-redis redis-cli HGETALL cost:total

# Backup
docker exec tekne-redis redis-cli BGSAVE
docker cp tekne-redis:/data/dump.rdb ./backup.rdb

# Reset via bot
/cost → Reset
```

## Bot Commands

- `/start` - Initialize bot
- `/proposal` - Start new proposal
- `/list` - List existing proposals
- `/cost` - View API costs
- `/checkupdate` - Update Typst templates from submodule

## Architecture

```
bot/               # Telegram handlers
agent/             # Agno AI agent + tools
  tools/           # Proposal, PDF, Git, Image tools
core/              # Cost tracking, Redis, callbacks
config.py          # Settings
main.py            # Entry point
```

### Submodule: tekne-proposals

The bot uses a **private Git submodule** for proposal templates and AI instructions:

```
submodules/tekne-proposals/
├── CLAUDE.md          # AI system prompt for proposal generation
├── docs/              # Client proposal examples
└── template.typ       # Typst PDF template
```

**Update templates:**
- Via bot: `/checkupdate` (runs `git submodule update --remote`)
- Manually: `git submodule update --init --recursive`

**Important:** This submodule is **private** and requires GitHub authentication for deployment.

## Tech Stack

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram integration
- [Agno](https://docs.agno.com) - AI agent framework
- [Typst](https://typst.app) - PDF typesetting
- Redis - Persistence
- Docker - Deployment
