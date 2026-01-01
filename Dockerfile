# Tekne Admin Bot - Production Dockerfile
FROM python:3.12.3-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including build tools for ruamel.yaml)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv
RUN uv sync --frozen

# Copy application code (submodules will be populated by Dokploy's git clone)
COPY . .

# Create data directory for cost tracking persistence
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the bot
CMD [".venv/bin/python", "main.py"]
