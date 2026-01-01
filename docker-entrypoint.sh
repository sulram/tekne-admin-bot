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

        # Add all current files to git
        git add .
        git commit -m "Initial commit from Docker deployment" || true

        # Create main branch
        git branch -M main

        cd /app
        echo "✅ Submodule git initialized"
    else
        echo "ℹ️  Submodule already has .git directory"
    fi

    # ALWAYS configure remote with token (even if .git exists)
    # This handles container restarts where GITHUB_TOKEN might change
    cd /app/submodules/tekne-proposals

    # Remove existing remote if present
    git remote remove origin 2>/dev/null || true

    # Configure remote URL with GitHub token if available
    if [ -n "$GITHUB_TOKEN" ]; then
        echo "✅ Configuring authenticated remote with GITHUB_TOKEN"
        git remote add origin "https://${GITHUB_TOKEN}@github.com/tekne-studio/tekne-proposals.git"

        # Configure git credential helper
        git config credential.helper store
    else
        echo "⚠️  No GITHUB_TOKEN - git push will not work"
        git remote add origin "https://github.com/tekne-studio/tekne-proposals.git"
    fi

    # Fetch and set up tracking
    if git fetch origin main 2>/dev/null; then
        echo "✅ Successfully connected to remote repository"
        git branch --set-upstream-to=origin/main main 2>/dev/null || true
    else
        echo "⚠️  Could not fetch from remote (check GITHUB_TOKEN)"
    fi

    cd /app
else
    echo "⚠️  Submodule directory not found at /app/submodules/tekne-proposals"
fi

# Start the bot
echo "🤖 Starting bot..."
exec .venv/bin/python main.py
