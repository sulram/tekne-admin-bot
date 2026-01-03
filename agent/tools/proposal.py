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
from ruamel.yaml import YAML

from config import SUBMODULE_PATH, DOCS_PATH
from core.callbacks import send_status

logger = logging.getLogger(__name__)

# Initialize ruamel.yaml for surgical edits (preserves formatting/comments)
ryaml = YAML()
ryaml.preserve_quotes = True
ryaml.default_flow_style = False


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

    # Validate YAML integrity immediately after save
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)  # Validate syntax (doesn't return content)
        logger.info(f"✅ YAML validation passed")
    except yaml.YAMLError as e:
        logger.error(f"❌ YAML validation failed: {e}")
        # Delete invalid file to prevent broken state
        file_path.unlink()
        return f"❌ Error: Generated YAML is invalid: {str(e)[:200]}"
    except Exception as e:
        logger.error(f"❌ Validation error: {e}")
        file_path.unlink()
        return f"❌ Error validating YAML: {str(e)[:200]}"

    relative_path = str(file_path.relative_to(SUBMODULE_PATH))
    logger.info(f"✅ Created proposal YAML: {relative_path}")
    send_status("📝 Criei o arquivo da proposta!")

    return relative_path


@tool
def load_proposal_yaml(yaml_file_path: str) -> str:
    """
    Load FULL proposal YAML (EXPENSIVE - avoid if possible!)

    **WARNING: This uses 10-20x more tokens than get_proposal_structure + read_section_content**
    ❌ **DO NOT use this to "verify" after update_proposal_field() - it's wasteful!**

    ONLY use when:
    - User explicitly asks to see entire proposal
    - Major restructuring (adding/removing sections, reordering)
    - You need to understand cross-section relationships

    ❌ **DO NOT USE TO VERIFY EDITS:**
    - After update_proposal_field() → Trust the ✅ confirmation!
    - To check if edit worked → It worked. Don't waste tokens.
    - To see new content → You already set it with new_value!

    For typical edits (change title, update section, fix typo):
    1. Use get_proposal_structure() to find section index
    2. Use read_section_content(index) if you need context
    3. Use update_proposal_field() to make the change (handles load/save internally)
    4. ❌ DO NOT call load_proposal_yaml() afterwards!

    Args:
        yaml_file_path: Relative path to YAML file from submodule root

    Returns:
        Full YAML content as string (~5000-10000 tokens)
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: Proposal not found: {yaml_file_path}"

    try:
        content = yaml_full_path.read_text(encoding='utf-8')
        token_estimate = len(content) // 4

        logger.info(f"📄 Loaded full proposal: {yaml_file_path}")
        logger.info(f"   Size: {len(content)} chars (~{token_estimate} tokens)")
        logger.info(f"   ⚠️  Consider using get_proposal_structure + read_section_content instead!")

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

    ⚠️  **CRITICAL: This tool loads the YAML INTERNALLY, edits it, and saves it.**
    ❌ **DO NOT call load_proposal_yaml() before or after this tool!**
    ✅ **You get a confirmation - trust it. No need to verify by loading YAML.**

    This is ideal for granular edits like fixing typos, updating a section title,
    or modifying specific bullet points.

    Workflow:
    1. Call update_proposal_field() → file is edited and saved internally
    2. You receive: "✅ Updated 'sections[8].content'"
    3. Generate PDF and commit
    4. ❌ DO NOT load YAML to "verify" the change

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
        Success message (NOT the full YAML!)
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: File not found: {yaml_file_path}"

    try:
        logger.info(f"🎯 update_proposal_field called:")
        logger.info(f"   File: {yaml_file_path}")
        logger.info(f"   Field: {field_path}")
        logger.info(f"   New value type: {type(new_value).__name__}")

        # Load existing YAML using ruamel.yaml (preserves formatting)
        with open(yaml_full_path, 'r', encoding='utf-8') as f:
            data = ryaml.load(f)

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

        # Save back to file using ruamel.yaml (preserves formatting/comments)
        with open(yaml_full_path, 'w', encoding='utf-8') as f:
            ryaml.dump(data, f)

        # Validate YAML integrity immediately after save
        validation_msg = ""
        try:
            with open(yaml_full_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)  # Validate syntax (doesn't return content)
            validation_msg = " | ✅ YAML válido"
            logger.info(f"✅ YAML validation passed")
        except yaml.YAMLError as e:
            validation_msg = f" | ⚠️ YAML inválido: {str(e)[:100]}"
            logger.error(f"❌ YAML validation failed: {e}")
        except Exception as e:
            validation_msg = f" | ⚠️ Erro validação: {str(e)[:100]}"
            logger.error(f"❌ Validation error: {e}")

        # Return minimal confirmation with validation status
        response_msg = f"✅ Updated '{field_path}'{validation_msg}"

        logger.info(f"✅ Successfully updated field in YAML:")
        logger.info(f"   Path: {field_path}")
        logger.info(f"   File: {yaml_file_path}")
        logger.info(f"   Response size: {len(response_msg)} chars (~{len(response_msg)//4} tokens)")

        # Create user-friendly status message with preview of new value
        field_name = field_path.split('.')[-1].split('[')[0]  # Extract readable field name
        value_preview = str(new_value)[:100]  # Truncate long values
        if len(str(new_value)) > 100:
            value_preview += "..."

        send_status(f"✅ {field_name.capitalize()} atualizado: \"{value_preview}\"")

        return response_msg

    except Exception as e:
        logger.error(f"Error updating field: {e}")
        return f"Error: {str(e)}"


@tool
def get_proposal_structure(yaml_file_path: str) -> str:
    """
    Get ONLY the structure/outline of a proposal without loading full content.

    **CRITICAL: Use this FIRST for ANY proposal edit request** (saves 90%+ tokens vs load_proposal_yaml)

    This shows section indices (for read_section_content/update_proposal_field) without wasting tokens.

    Use when you need to:
    - Navigate sections ("which section has the budget?") → Returns section indices
    - Locate content for editing → Get index, then use read_section_content() or update_proposal_field()
    - Count elements ("how many bullets in section 2?")
    - See section titles and basic metadata

    DO NOT use load_proposal_yaml() unless user explicitly asks to see entire proposal.

    Args:
        yaml_file_path: Relative path to YAML file (e.g., "docs/2026-01-client/proposta-x.yml")

    Returns:
        Compact outline with section indices [0], [1], etc. for navigation
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: File not found: {yaml_file_path}"

    try:
        with open(yaml_full_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Build compact structure
        meta = data.get('meta', {})
        sections = data.get('sections', [])

        # Format output (minimal tokens)
        result = []
        result.append(f"📄 {meta.get('title', 'Sem título')}")
        result.append(f"👤 Cliente: {meta.get('client', 'N/A')}")
        result.append(f"📅 Data: {meta.get('date', 'N/A')}")
        result.append("")
        result.append(f"📑 Seções ({len(sections)}):")

        for i, section in enumerate(sections):
            title = section.get('title', f'Seção {i}')
            result.append(f"  [{i}] {title}")

            # Add compact metadata about section content
            details = []
            if section.get('content'):
                content_len = len(section['content'])
                details.append(f"{content_len} chars")

            if 'bullets' in section:
                bullet_count = len(section['bullets'])
                details.append(f"{bullet_count} bullets")

            if 'subsections' in section:
                subsection_count = len(section['subsections'])
                details.append(f"{subsection_count} subsections")

            if 'budget' in section:
                details.append("budget")

            if 'profiles' in section:
                profile_count = len(section['profiles'])
                details.append(f"{profile_count} profiles")

            if details:
                result.append(f"      → {', '.join(details)}")

        output = "\n".join(result)
        full_yaml_size = len(str(data))
        token_estimate = len(output) // 4
        savings_pct = ((full_yaml_size - len(output)) / full_yaml_size * 100) if full_yaml_size > 0 else 0

        logger.info(f"📋 Structure: {len(output)} chars (~{token_estimate} tokens)")
        logger.info(f"   vs Full YAML: {full_yaml_size} chars (~{full_yaml_size//4} tokens)")
        logger.info(f"   💰 Savings: {savings_pct:.1f}% fewer tokens")

        return output

    except Exception as e:
        logger.error(f"Error reading structure: {e}")
        return f"Error: {str(e)}"


@tool
def read_section_content(
    yaml_file_path: str,
    section_index: int
) -> str:
    """
    Read ONLY a specific section's content without loading the entire proposal.

    This is much more efficient than load_proposal_yaml() when you need:
    - Content of one section for editing
    - Context for adding/modifying text in a section
    - Viewing a specific section

    Args:
        yaml_file_path: Relative path to YAML file (e.g., "docs/2026-01-client/proposta-x.yml")
        section_index: Section index (0-based, from get_proposal_structure)

    Returns:
        Section data including title, content, bullets, subsections
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: File not found: {yaml_file_path}"

    try:
        with open(yaml_full_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        sections = data.get('sections', [])

        if section_index < 0 or section_index >= len(sections):
            return f"Error: Section index {section_index} out of range (0-{len(sections)-1})"

        section = sections[section_index]

        # Format section content
        result = []
        result.append(f"📑 Section [{section_index}]: {section.get('title', 'Untitled')}")
        result.append("")

        # Content
        if 'content' in section:
            result.append("📝 Content:")
            result.append(section['content'])
            result.append("")

        # Bullets
        if 'bullets' in section:
            result.append(f"🔸 Bullets ({len(section['bullets'])}):")
            for i, bullet in enumerate(section['bullets']):
                result.append(f"  [{i}] {bullet}")
            result.append("")

        # Subsections
        if 'subsections' in section:
            result.append(f"📂 Subsections ({len(section['subsections'])}):")
            for i, subsection in enumerate(section['subsections']):
                result.append(f"  [{i}] {subsection.get('name', 'Untitled')}")
                if 'bullets' in subsection:
                    result.append(f"      → {len(subsection['bullets'])} bullets")
            result.append("")

        # Budget (if present)
        if 'budget' in section:
            budget = section['budget']
            result.append("💰 Budget:")
            result.append(f"  Subtotal: {budget.get('subtotal', 'N/A')}")
            if 'discount' in budget:
                result.append(f"  Discount: {budget.get('discount')}")
            result.append(f"  Total: {budget.get('total', 'N/A')}")
            result.append("")

        # Profiles (if present)
        if 'profiles' in section:
            result.append(f"👥 Profiles ({len(section['profiles'])}):")
            for i, profile in enumerate(section['profiles']):
                result.append(f"  [{i}] {profile.get('name', 'Unnamed')}")
            result.append("")

        output = "\n".join(result)
        full_yaml_size = len(str(data))
        token_estimate = len(output) // 4
        savings_pct = ((full_yaml_size - len(output)) / full_yaml_size * 100) if full_yaml_size > 0 else 0

        logger.info(f"📖 Section {section_index}: {len(output)} chars (~{token_estimate} tokens)")
        logger.info(f"   vs Full YAML: {full_yaml_size} chars (~{full_yaml_size//4} tokens)")
        logger.info(f"   💰 Savings: {savings_pct:.1f}% fewer tokens")

        return output

    except Exception as e:
        logger.error(f"Error reading section: {e}")
        return f"Error: {str(e)}"


def _list_proposals_impl(limit: int = 10) -> str:
    """
    Internal implementation: List existing proposals in docs/ directory
    This is the actual function that does the work, callable from anywhere.

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

    # Normalize dates to strings for consistent sorting
    # YAML may parse dates as datetime.date or keep them as strings if quoted
    for p in proposals:
        date_value = p.get('date', '')
        if hasattr(date_value, 'isoformat'):  # datetime.date or datetime.datetime
            p['date'] = date_value.isoformat()
        elif not isinstance(date_value, str):
            p['date'] = str(date_value)

    # Sort by date (DESC) then by folder name (DESC)
    # This ensures proposals within same folder are also sorted by date
    proposals.sort(key=lambda p: (p.get('date', ''), p.get('path', '')), reverse=True)

    # Limit to most recent N proposals
    proposals = proposals[:limit]

    # Format output
    formatted = []
    for i, p in enumerate(proposals, 1):
        formatted.append(f"{i}. 📄 {p['path']}\n   Cliente: {p['client']}\n   Título: {p['title']}\n   Data: {p['date']}")

    return f"Propostas mais recentes ({len(proposals)}):\n\n" + "\n\n".join(formatted)


# Simple function for direct use (bot commands, etc)
list_existing_proposals = _list_proposals_impl


# Agent-compatible wrapper with @tool decorator
@tool
def list_existing_proposals_tool(limit: int = 10) -> str:
    """
    List existing proposals in docs/ directory, sorted by date (Agent tool wrapper)

    Args:
        limit: Maximum number of proposals to return (default: 10)

    Returns:
        Formatted list of proposals with their paths
    """
    return _list_proposals_impl(limit)


@tool
def delete_proposal(yaml_file_path: str) -> str:
    """
    Delete an entire proposal folder (including YAML, PDFs, and images).

    WARNING: This operation cannot be undone! The entire project folder will be permanently deleted.

    Args:
        yaml_file_path: Relative path to any YAML file in the folder (e.g., "docs/2026-01-client/proposta-x.yml")
                       The entire parent folder will be deleted.

    Returns:
        Success message or error

    Example:
        - delete_proposal("docs/2026-01-test/proposta-demo.yml") → Deletes entire "2026-01-test" folder
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: File not found: {yaml_file_path}"

    try:
        # Always delete entire project folder
        folder_path = yaml_full_path.parent
        folder_name = folder_path.name

        # Safety check: ensure it's in docs/ and looks like a project folder
        if not str(folder_path).startswith(str(DOCS_PATH)):
            return f"Error: Path is not in docs/ directory: {folder_path}"

        # Count files in folder
        files_in_folder = list(folder_path.glob("*"))
        file_count = len(files_in_folder)

        # List files for logging
        file_names = [f.name for f in files_in_folder]
        logger.info(f"📋 Files to be deleted: {', '.join(file_names)}")

        # Delete folder and all contents
        import shutil
        shutil.rmtree(folder_path)

        logger.info(f"🗑️  Deleted entire folder: {folder_name} ({file_count} files)")
        send_status(f"🗑️ Deletei a pasta '{folder_name}' com {file_count} arquivo(s)")

        return f"✅ Deleted entire folder: {folder_name} ({file_count} files: {', '.join(file_names)})\n\n⚠️ Remember to commit and push this change using commit_and_push_submodule!"

    except Exception as e:
        logger.error(f"Error deleting proposal: {e}", exc_info=True)
        return f"Error: {str(e)}"
