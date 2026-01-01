# Dokploy Deployment Guide

## Prerequisites

1. **GitHub Personal Access Token** for private `tekne-proposals` submodule
   - Go to: https://github.com/settings/tokens
   - Generate new token (classic)
   - Permissions: `repo` (Full control of private repositories)
   - Copy the token

## Dokploy Configuration

### 1. Repository Settings

In Dokploy app configuration:

**Option A: Use GitHub App (Recommended)**
- Connect Dokploy GitHub App
- Grant access to both repositories:
  - `tekne-studio/tekne-admin-bot`
  - `tekne-studio/tekne-proposals`

**Option B: Use Personal Access Token**
- Repository URL: `https://<TOKEN>@github.com/tekne-studio/tekne-admin-bot.git`
- Replace `<TOKEN>` with your GitHub Personal Access Token

### 2. Environment Variables

Set these in Dokploy Environment Variables:

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
ALLOWED_USERS=27463101  # Comma-separated user IDs

# Optional: GitHub token for git push operations (if bot needs to commit proposals)
GITHUB_TOKEN=your_github_personal_access_token
```

**Note:** `GITHUB_TOKEN` is only needed if you want the bot to automatically commit and push proposal changes to the repository. Without it, the bot can still read and generate PDFs, but cannot push updates.

### 3. Build Settings

- **Build Type**: Dockerfile
- **Dockerfile Path**: `./Dockerfile`
- **Docker Compose**: Optional (can use docker-compose.yml)

### 4. Deploy

Click "Deploy" and monitor logs for:
- ✅ Submodule cloned successfully
- ✅ Dependencies installed
- ✅ Bot started

## Troubleshooting

### Submodule Authentication Failed

**Error:**
```
fatal: could not read Username for 'https://github.com': No such device or address
```

**Solution:**
1. Make sure GitHub token has `repo` permission
2. In Dokploy, use GitHub App authentication OR
3. Include token in repository URL

### Alternative: Public Submodule

If you can make `tekne-proposals` public:
1. Go to GitHub → tekne-proposals → Settings
2. Scroll to "Danger Zone"
3. Change visibility to "Public"
4. Re-deploy in Dokploy

### Alternative: Remove Submodule Dependency

If authentication is too complex, copy proposal files directly:

```bash
# Copy proposals to main repo
cp -r submodules/tekne-proposals/docs ./proposals
git add proposals
git commit -m "Include proposals directly (no submodule)"

# Update config.py
SUBMODULE_PATH = Path(__file__).parent / "proposals"
```

## Monitoring

After deployment:
- Check logs: `docker-compose logs -f`
- Test bot: Send `/help` to your Telegram bot
- Monitor costs: Send `/cost` command

## Restart Policy

The bot is configured to auto-restart on crashes:
- `restart: always` in docker-compose.yml
- Exit code 1 triggers Docker restart
- Graceful shutdown on Ctrl+C (exit code 0)
