"""
Routing and Context Tools for Leader Agent

These tools help Leader extract context from messages and manage project sessions.
They DO NOT make routing decisions - that's the Leader's job via LLM intelligence.
"""

import logging
import re
from typing import Optional
from agno.tools import tool

logger = logging.getLogger(__name__)


@tool
def identify_client_project(message: str, session_context: str = "") -> dict:
    """
    Extract client and project names from user message or session context.

    This tool analyzes the message for project-related information like:
    - Client names (e.g., "ACME", "TechCorp")
    - Project names (e.g., "website redesign", "mobile app")

    Args:
        message: User's message
        session_context: Current session context (optional)

    Returns:
        dict with client, project, confidence, and context info
    """
    result = {
        "client": None,
        "project": None,
        "confidence": "low",
        "context": session_context,
        "inferred": False
    }

    # Extract client from session_context if available (format: user_id:yyyy-mm-client-project)
    if session_context and ":" in session_context:
        parts = session_context.split(":")
        if len(parts) >= 2 and "-" in parts[1]:
            # Parse yyyy-mm-client-project
            session_parts = parts[1].split("-", 2)  # Split only first 2 dashes
            if len(session_parts) == 3:
                # Format: yyyy-mm-rest
                date_client_project = session_parts[2]
                if "-" in date_client_project:
                    client_project = date_client_project.split("-", 1)
                    result["client"] = client_project[0]
                    result["project"] = client_project[1] if len(client_project) > 1 else None
                    result["confidence"] = "high"
                    result["inferred"] = True
                    logger.info(f"Extracted from session: client={result['client']}, project={result['project']}")
                    return result

    # Try to extract from message (simple heuristics)
    # Look for common patterns: "para [CLIENT]", "projeto [PROJECT]", etc.
    message_lower = message.lower()

    # Client patterns
    client_patterns = [
        r'para\s+(?:a\s+)?([A-Z][A-Za-z0-9\s]+?)(?:\s+sobre|\s+projeto|\s*$|\.)',
        r'cliente\s+([A-Z][A-Za-z0-9\s]+?)(?:\s|$|\.)',
        r'(?:^|\s)([A-Z][A-Z0-9]+)(?:\s+Corp|\s+Inc|\s+Ltd)?(?:\s|$)',
    ]

    for pattern in client_patterns:
        match = re.search(pattern, message)
        if match:
            result["client"] = match.group(1).strip()
            result["confidence"] = "medium"
            break

    # Project patterns
    project_patterns = [
        r'projeto\s+([a-z0-9\-\s]+?)(?:\s+para|\s*$|\.)',
        r'sobre\s+([a-z0-9\-\s]+?)(?:\s+para|\s*$|\.)',
    ]

    for pattern in project_patterns:
        match = re.search(pattern, message_lower)
        if match:
            result["project"] = match.group(1).strip()
            if result["client"]:
                result["confidence"] = "high"
            break

    logger.info(f"Identified: client={result['client']}, project={result['project']}, confidence={result['confidence']}")
    return result


@tool
def prepare_new_project_context(client: str, project: str) -> dict:
    """
    Prepare file paths and context for a new or existing project.

    Creates standardized paths following the naming convention:
    yyyy-mm-client-projectslug.yaml

    Args:
        client: Client name (e.g., "ACME")
        project: Project name (e.g., "website redesign")

    Returns:
        dict with paths, existence status, and session_id suffix
    """
    from datetime import datetime
    from pathlib import Path
    from config import SUBMODULE_PATH

    # Sanitize names for filesystem
    client_slug = client.lower().replace(" ", "-")
    project_slug = project.lower().replace(" ", "-")

    # Generate yyyy-mm prefix
    now = datetime.now()
    date_prefix = now.strftime("%Y-%m")

    # Build filename: yyyy-mm-client-project.yaml
    filename = f"{date_prefix}-{client_slug}-{project_slug}.yaml"

    # Paths
    docs_path = Path(SUBMODULE_PATH) / "docs"
    yaml_path = docs_path / filename
    pdf_path = docs_path / filename.replace(".yaml", ".pdf")

    # Check if project already exists
    exists = yaml_path.exists()

    # Session ID suffix (for Redis session key)
    session_suffix = f"{date_prefix}-{client_slug}-{project_slug}"

    result = {
        "client": client,
        "project": project,
        "yaml_path": str(yaml_path),
        "pdf_path": str(pdf_path),
        "filename": filename,
        "exists": exists,
        "session_id_suffix": session_suffix,
        "directory": str(docs_path),
    }

    logger.info(f"Prepared context: {filename}, exists={exists}")
    return result


logger.info("✅ Routing tools loaded (identify_client_project, prepare_new_project_context)")
