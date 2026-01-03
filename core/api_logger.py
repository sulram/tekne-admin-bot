"""
API call logging utilities

Provides detailed logging of HTTP requests to external APIs (Anthropic, etc)
without flooding logs with raw request/response bodies.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def log_api_call(
    method: str,
    url: str,
    model: Optional[str] = None,
    tokens_sent: Optional[int] = None,
    tokens_received: Optional[int] = None,
    duration_ms: Optional[int] = None,
    status_code: Optional[int] = None,
    error: Optional[str] = None
):
    """
    Log an API call with relevant details

    Args:
        method: HTTP method (GET, POST, etc)
        url: API endpoint URL
        model: Model name if applicable (e.g., "claude-3-5-sonnet-20241022")
        tokens_sent: Input tokens sent
        tokens_received: Output tokens received
        duration_ms: Request duration in milliseconds
        status_code: HTTP status code
        error: Error message if request failed
    """
    # Extract endpoint from URL (remove query params, just show path)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        endpoint = parsed.path
    except:
        endpoint = url

    # Build log message
    parts = [f"🌐 {method} {endpoint}"]

    if model:
        parts.append(f"| Model: {model}")

    if tokens_sent is not None or tokens_received is not None:
        token_info = []
        if tokens_sent:
            token_info.append(f"{tokens_sent:,} in")
        if tokens_received:
            token_info.append(f"{tokens_received:,} out")
        if token_info:
            parts.append(f"| Tokens: {' + '.join(token_info)}")

    if duration_ms is not None:
        parts.append(f"| {duration_ms}ms")

    if status_code is not None:
        status_emoji = "✅" if 200 <= status_code < 300 else "❌"
        parts.append(f"| {status_emoji} {status_code}")

    if error:
        parts.append(f"| Error: {error}")

    log_msg = " ".join(parts)

    if error or (status_code and status_code >= 400):
        logger.error(log_msg)
    else:
        logger.info(log_msg)


def log_tool_call(tool_name: str, agent_name: Optional[str] = None, duration_s: Optional[float] = None):
    """
    Log a tool call

    Args:
        tool_name: Name of the tool being called
        agent_name: Name of agent calling the tool
        duration_s: Execution time in seconds
    """
    parts = [f"🔧 {tool_name}"]

    if agent_name:
        parts.append(f"(by {agent_name})")

    if duration_s is not None:
        parts.append(f"- {duration_s:.2f}s")

    logger.info(" ".join(parts))


def log_delegation(from_agent: str, to_agent: str, reason: Optional[str] = None):
    """
    Log delegation from one agent to another

    Args:
        from_agent: Agent delegating the task
        to_agent: Agent receiving the task
        reason: Optional reason for delegation
    """
    parts = [f"🎯 {from_agent} → {to_agent}"]

    if reason:
        parts.append(f"| {reason}")

    logger.info(" ".join(parts))
