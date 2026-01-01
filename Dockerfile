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
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Typst (required for PDF generation)
# Using gnu binary for Debian/Ubuntu (glibc), not musl (Alpine)
RUN wget https://github.com/typst/typst/releases/download/v0.12.0/typst-x86_64-unknown-linux-gnu.tar.xz \
    && tar -xf typst-x86_64-unknown-linux-gnu.tar.xz \
    && mv typst-x86_64-unknown-linux-gnu/typst /usr/local/bin/typst \
    && rm -rf typst-x86_64-unknown-linux-gnu* \
    && chmod +x /usr/local/bin/typst \
    && typst --version

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
