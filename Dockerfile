# Tekne Admin Bot - Production Dockerfile
FROM python:3.12.3-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including build tools for ruamel.yaml and Typst)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gcc \
    python3-dev \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required for Typst installation via Cargo)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Typst via Cargo (most reliable method for Docker)
RUN cargo install --locked typst-cli \
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
