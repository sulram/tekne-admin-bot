"""
Proposal management tools
"""

import yaml
import logging
import unicodedata
from datetime import datetime
from typing import Optional
from pathlib import Path
from agno.tools import tool

from config import SUBMODULE_PATH, DOCS_PATH
from core.callbacks import send_status

logger = logging.getLogger(__name__)


def normalize_slug(text: str) -> str:
    """
    Normalize text to create a safe filename slug:
    - Remove accents and special characters
    - Convert to lowercase
    - Replace spaces/underscores with hyphens
    - Remove consecutive hyphens
    """
    # Normalize unicode characters (remove accents)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = text.replace(" ", "-").replace("_", "-")

    # Keep only alphanumeric and hyphens
    text = ''.join(char for char in text if char.isalnum() or char == '-')

    # Remove consecutive hyphens
    while '--' in text:
        text = text.replace('--', '-')

    # Remove leading/trailing hyphens
    text = text.strip('-')

    return text


@tool
def save_proposal_yaml(
    yaml_content: str,
    client_name: str = "",
    project_slug: str = "",
    date: Optional[str] = None,
    existing_file_path: Optional[str] = None
) -> str:
    """
    Save proposal YAML to submodules/tekne-proposals/docs/

    To EDIT an existing proposal, provide existing_file_path parameter.
    To CREATE a new proposal, provide client_name and project_slug.

    Args:
        yaml_content: The complete YAML content
        client_name: Client name for folder (will be slugified) - required for new proposals
        project_slug: Project name for filename (will be slugified) - required for new proposals
        date: Optional date in YYYY-MM-DD format (defaults to today)
        existing_file_path: Path to existing file to update (e.g., "docs/2025-12-sesc/proposta-metaverso.yml")

    Returns:
        Path to the saved file
    """
    # If editing existing file, use that path
    if existing_file_path:
        file_path = SUBMODULE_PATH / existing_file_path

        if not file_path.exists():
            return f"Error: File not found: {existing_file_path}"

        file_path.write_text(yaml_content, encoding="utf-8")
        relative_path = str(file_path.relative_to(SUBMODULE_PATH))
        logger.info(f"✅ Updated proposal YAML: {relative_path}")
        send_status("📝 Atualizei o arquivo da proposta!")
        return relative_path

    # Creating new proposal
    if not client_name or not project_slug:
        return "Error: client_name and project_slug are required for new proposals"

    # Parse date
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    year_month = date[:7]  # YYYY-MM

    # Normalize slugs (remove accents, special chars)
    client_slug = normalize_slug(client_name)
    project_slug = normalize_slug(project_slug)

    # Create directory path: docs/YYYY-MM-client-slug/
    dir_name = f"{year_month}-{client_slug}"
    dir_path = DOCS_PATH / dir_name
    dir_path.mkdir(parents=True, exist_ok=True)

    # Create file path: proposta-project-slug.yml
    file_name = f"proposta-{project_slug}.yml"
    file_path = dir_path / file_name

    # Save YAML
    file_path.write_text(yaml_content, encoding="utf-8")

    relative_path = str(file_path.relative_to(SUBMODULE_PATH))
    logger.info(f"✅ Created proposal YAML: {relative_path}")
    send_status("📝 Criei o arquivo da proposta!")

    return relative_path


@tool
def load_proposal_yaml(yaml_file_path: str) -> str:
    """
    Load existing proposal YAML for editing

    Args:
        yaml_file_path: Relative path to YAML file from submodule root

    Returns:
        YAML content as string
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: Proposal not found: {yaml_file_path}"

    try:
        content = yaml_full_path.read_text(encoding='utf-8')
        logger.info(f"Loaded proposal: {yaml_file_path} ({len(content)} chars)")

        # Return YAML directly without markdown formatting to save tokens
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def update_proposal_field(
    yaml_file_path: str,
    field_path: str,
    new_value: str | list | dict
) -> str:
    """
    Update a specific field in a proposal YAML without rewriting the entire file.

    This is ideal for granular edits like fixing typos, updating a section title,
    or modifying specific bullet points.

    Args:
        yaml_file_path: Relative path to YAML file (e.g., "docs/2026-01-client/proposta-x.yml")
        field_path: Dot notation path to field (examples below)
        new_value: New value for the field (string, list, or dict)

    Field path examples:
        - "meta.title" → Update proposal title
        - "meta.client" → Update client name
        - "meta.date" → Update date
        - "sections[0].title" → Update first section's title
        - "sections[1].content" → Update second section's content
        - "sections[0].bullets" → Update entire bullets list
        - "sections[0].bullets[2]" → Update third bullet point
        - "sections[0].image" → Update section image path

    Returns:
        Success message or error
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: File not found: {yaml_file_path}"

    try:
        logger.info(f"🎯 update_proposal_field called:")
        logger.info(f"   File: {yaml_file_path}")
        logger.info(f"   Field: {field_path}")
        logger.info(f"   New value type: {type(new_value).__name__}")

        # Load existing YAML
        with open(yaml_full_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Parse field path (e.g., "sections[0].title" or "meta.client")
        parts = []
        current = ""
        in_bracket = False

        for char in field_path:
            if char == '[':
                if current:
                    parts.append(current)
                    current = ""
                in_bracket = True
            elif char == ']':
                if current:
                    parts.append(int(current))
                    current = ""
                in_bracket = False
            elif char == '.' and not in_bracket:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += char

        if current:
            parts.append(current)

        # Navigate to parent and update
        if not parts:
            return "Error: Empty field path"

        # Navigate to the field
        target = data
        for i, part in enumerate(parts[:-1]):
            if isinstance(part, int):
                if not isinstance(target, list):
                    return f"Error: Expected list at {'.'.join(map(str, parts[:i]))}"
                if part >= len(target):
                    return f"Error: Index {part} out of range at {'.'.join(map(str, parts[:i]))}"
                target = target[part]
            else:
                if not isinstance(target, dict):
                    return f"Error: Expected dict at {'.'.join(map(str, parts[:i]))}"
                if part not in target:
                    return f"Error: Key '{part}' not found at {'.'.join(map(str, parts[:i]))}"
                target = target[part]

        # Update the final field
        final_key = parts[-1]
        if isinstance(final_key, int):
            if not isinstance(target, list):
                return f"Error: Expected list for index access"
            if final_key >= len(target):
                return f"Error: Index {final_key} out of range"
            target[final_key] = new_value
        else:
            if not isinstance(target, dict):
                return f"Error: Expected dict for key access"
            target[final_key] = new_value

        # Save back to file
        with open(yaml_full_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        logger.info(f"✅ Successfully updated field in YAML:")
        logger.info(f"   Path: {field_path}")
        logger.info(f"   File: {yaml_file_path}")
        send_status(f"✏️ Atualizei o campo '{field_path}'!")

        return f"✅ Successfully updated {field_path} in {yaml_file_path}"

    except Exception as e:
        logger.error(f"Error updating field: {e}")
        return f"Error: {str(e)}"


@tool
def list_existing_proposals(limit: int = 10) -> str:
    """
    List existing proposals in docs/ directory, sorted by date (most recent first)

    Args:
        limit: Maximum number of proposals to return (default: 10)

    Returns:
        Formatted list of proposals with their paths
    """
    if not DOCS_PATH.exists():
        return "No proposals found. docs/ directory doesn't exist."

    proposals = []
    for project_dir in sorted(DOCS_PATH.iterdir(), reverse=True):  # Reverse sort for most recent first
        if project_dir.is_dir():
            # Find YAML files in directory
            yaml_files = list(project_dir.glob("*.yml"))
            for yaml_file in yaml_files:
                try:
                    # Read YAML to get title/client
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        meta = data.get('meta', {})
                        title = meta.get('title', 'Sem título')
                        client = meta.get('client', 'Sem cliente')
                        date = meta.get('date', 'Sem data')

                        proposals.append({
                            'path': f"{project_dir.name}/{yaml_file.name}",
                            'client': client,
                            'title': title,
                            'date': date
                        })
                except Exception as e:
                    proposals.append({
                        'path': f"{project_dir.name}/{yaml_file.name}",
                        'client': 'Erro',
                        'title': 'Erro ao ler',
                        'date': 'N/A'
                    })

    if not proposals:
        return "Nenhuma proposta encontrada em docs/"

    # Limit to most recent N proposals
    proposals = proposals[:limit]

    # Format output
    formatted = []
    for i, p in enumerate(proposals, 1):
        formatted.append(f"{i}. 📄 {p['path']}\n   Cliente: {p['client']}\n   Título: {p['title']}\n   Data: {p['date']}")

    return f"Propostas mais recentes ({len(proposals)}):\n\n" + "\n\n".join(formatted)
