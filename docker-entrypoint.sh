#!/bin/bash
set -e

echo "🚀 Tekne Admin Bot - Docker Entrypoint"

# Check if submodule directory exists and needs git initialization
if [ -d "/app/submodules/tekne-proposals" ]; then
    # Remove broken gitlink if it exists (points to non-existent parent .git)
    if [ -f "/app/submodules/tekne-proposals/.git" ]; then
        echo "📦 Removing broken gitlink and initializing fresh git repository..."
        rm -f /app/submodules/tekne-proposals/.git
    fi

    # Only initialize if no .git directory exists
    if [ ! -d "/app/submodules/tekne-proposals/.git" ]; then
        echo "📦 Cloning submodule from remote repository..."

        # Build remote URL with token if available
        if [ -n "$GITHUB_TOKEN" ]; then
            REMOTE_URL="https://${GITHUB_TOKEN}@github.com/tekne-studio/tekne-proposals.git"
        else
            REMOTE_URL="https://github.com/tekne-studio/tekne-proposals.git"
            echo "⚠️  No GITHUB_TOKEN - git push will not work"
        fi

        # Clone into temporary directory
        git clone "$REMOTE_URL" /tmp/tekne-proposals-clone

        # Move .git directory to submodule path
        mv /tmp/tekne-proposals-clone/.git /app/submodules/tekne-proposals/.git

        # Clean up temp clone
        rm -rf /tmp/tekne-proposals-clone

        cd /app/submodules/tekne-proposals

        # Configure git user (required for commits)
        git config user.name "Tekne Admin Bot"
        git config user.email "bot@tekne.studio"

        # Reset to match remote exactly (keep local files that might have been copied by Docker)
        git reset --hard HEAD

        echo "✅ Submodule cloned from remote with full history"
        cd /app
    else
        echo "ℹ️  Submodule already has .git directory"

        # Even if .git exists, ensure remote is configured correctly
        cd /app/submodules/tekne-proposals

        # Remove existing remote if present
        git remote remove origin 2>/dev/null || true

        # Configure remote URL with GitHub token
        if [ -n "$GITHUB_TOKEN" ]; then
            echo "✅ Configuring authenticated remote with GITHUB_TOKEN"
            git remote add origin "https://${GITHUB_TOKEN}@github.com/tekne-studio/tekne-proposals.git"
            git config credential.helper store
        else
            echo "⚠️  No GITHUB_TOKEN - git push will not work"
            git remote add origin "https://github.com/tekne-studio/tekne-proposals.git"
        fi

        # Configure git user
        git config user.name "Tekne Admin Bot"
        git config user.email "bot@tekne.studio"

        # Fetch and set up tracking
        if git fetch origin main 2>/dev/null; then
            echo "✅ Successfully connected to remote repository"
            git branch --set-upstream-to=origin/main main 2>/dev/null || true
        else
            echo "⚠️  Could not fetch from remote (check GITHUB_TOKEN)"
        fi

        cd /app
    fi
else
    echo "⚠️  Submodule directory not found at /app/submodules/tekne-proposals"
fi

# Start the bot
echo "🤖 Starting bot..."
exec .venv/bin/python main.py
