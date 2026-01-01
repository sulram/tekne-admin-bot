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
        echo "📦 Initializing submodule git repository..."
        cd /app/submodules/tekne-proposals

        # Initialize git repository
        git init

    # Configure git user (required for commits)
    git config user.name "Tekne Admin Bot"
    git config user.email "bot@tekne.studio"

    # Configure remote URL with GitHub token if available
    if [ -n "$GITHUB_TOKEN" ]; then
        echo "✅ GitHub token found, configuring authenticated remote"
        git remote add origin "https://${GITHUB_TOKEN}@github.com/tekne-studio/tekne-proposals.git"

        # Configure git credential helper to cache token
        git config credential.helper store
    else
        echo "⚠️  No GITHUB_TOKEN environment variable - git push will not work"
        git remote add origin "https://github.com/tekne-studio/tekne-proposals.git"
    fi

    # Add all current files to git
    git add .
    git commit -m "Initial commit from Docker deployment" || true

    # Fetch and set up tracking
    if git fetch origin main 2>/dev/null; then
        echo "✅ Successfully connected to remote repository"
        git branch -M main
        git branch --set-upstream-to=origin/main main
    else
        echo "⚠️  Could not fetch from remote (check GITHUB_TOKEN if push is needed)"
        git branch -M main
    fi

        cd /app
        echo "✅ Submodule git initialized"
    else
        echo "ℹ️  Submodule already has .git directory"
    fi
else
    echo "⚠️  Submodule directory not found at /app/submodules/tekne-proposals"
fi

# Start the bot
echo "🤖 Starting bot..."
exec .venv/bin/python main.py
