# Tekne Admin Bot - Production Dockerfile

# Stage 1: Get Typst binary from official image
FROM ghcr.io/typst/typst:latest AS typst

# Stage 2: Main application
FROM python:3.12.3-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including build tools for ruamel.yaml)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gcc \
    python3-dev \
    wget \
    unzip \
    fontconfig \
    fonts-lxgw-wenkai \
    && rm -rf /var/lib/apt/lists/*

# Copy Typst binary from official image
COPY --from=typst /bin/typst /usr/local/bin/typst
RUN chmod +x /usr/local/bin/typst && typst --version

# Install Space Grotesk font (required by proposal template)
# LXGW WenKai (霞鹜文楷) is already installed via apt - traditional Kaiti-style font for CJK
# Typst uses ~/.local/share/fonts for user fonts
RUN mkdir -p /root/.local/share/fonts/space-grotesk && \
    cd /tmp && \
    wget -q https://github.com/floriankarsten/space-grotesk/releases/download/2.0.0/SpaceGrotesk-2.0.0.zip && \
    unzip -q SpaceGrotesk-2.0.0.zip -d space-grotesk && \
    find space-grotesk -name "*.otf" -exec cp {} /root/.local/share/fonts/space-grotesk/ \; && \
    find space-grotesk -name "*.ttf" -exec cp {} /root/.local/share/fonts/space-grotesk/ \; && \
    rm -rf /tmp/space-grotesk /tmp/SpaceGrotesk-2.0.0.zip && \
    fc-cache -fv && \
    ls -lah /root/.local/share/fonts/space-grotesk/ && \
    echo "✅ Fonts installed: Space Grotesk + LXGW WenKai (Kaiti style)"

# Install uv for faster Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv
RUN uv sync --frozen

# Copy application code (submodules will be populated by Dokploy's git clone)
COPY . .

# Copy and set executable permissions for entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create data directory for cost tracking persistence
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Use entrypoint script to initialize git before starting bot
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
