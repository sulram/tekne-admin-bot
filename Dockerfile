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
    && rm -rf /var/lib/apt/lists/*

# Copy Typst binary from official image
COPY --from=typst /bin/typst /usr/local/bin/typst
RUN chmod +x /usr/local/bin/typst && typst --version

# Install Space Grotesk font (required by proposal template)
RUN mkdir -p /usr/share/fonts/truetype/space-grotesk && \
    cd /tmp && \
    wget -q https://github.com/floriankarsten/space-grotesk/releases/download/2.0.0/SpaceGrotesk-2.0.0.zip && \
    unzip -q SpaceGrotesk-2.0.0.zip -d space-grotesk && \
    cp space-grotesk/fonts/otf/*.otf /usr/share/fonts/truetype/space-grotesk/ && \
    fc-cache -fv && \
    rm -rf /tmp/space-grotesk /tmp/SpaceGrotesk-2.0.0.zip && \
    echo "✅ Space Grotesk font installed"

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
