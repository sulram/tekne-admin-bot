"""
Cleanup and maintenance tools for proposal repository

Handles:
- Orphaned PDFs (PDFs without corresponding YAML)
- Orphaned images (images not referenced in any YAML)
- Empty directories
- Renaming for consistency
- Validation of proposal structure
"""

import logging
from pathlib import Path
from agno.tools import tool

logger = logging.getLogger(__name__)

PROPOSALS_DIR = Path("submodules/tekne-proposals")


@tool
def cleanup_orphaned_files() -> str:
    """
    Remove orphaned PDFs and images from proposals repository.

    Orphaned PDFs: PDF files without a corresponding YAML file
    Orphaned images: Image files not referenced in any YAML file

    Returns:
        str: Summary of cleanup actions performed
    """
    # TODO: Implement cleanup logic
    logger.info("🧹 cleanup_orphaned_files() - TODO")
    return "TODO: Implementar lógica de cleanup"


@tool
def rename_proposal_directory(old_name: str, new_name: str) -> str:
    """
    Rename a proposal directory maintaining consistency.

    Args:
        old_name: Current directory name (e.g., "2026-01-sesc-friburgo")
        new_name: New directory name (e.g., "2026-02-sesc-friburgo")

    Returns:
        str: Confirmation message with new path, or error message
    """
    import shutil

    old_path = PROPOSALS_DIR / "docs" / old_name
    new_path = PROPOSALS_DIR / "docs" / new_name

    if not old_path.exists():
        return f"❌ Diretório não encontrado: {old_name}"

    if new_path.exists():
        return f"❌ Diretório destino já existe: {new_name}"

    try:
        shutil.move(str(old_path), str(new_path))
        logger.info(f"✅ Renamed {old_name} → {new_name}")

        # Find YAML file in new location
        yaml_files = list(new_path.glob("*.yml")) + list(new_path.glob("*.yaml"))
        if yaml_files:
            new_yaml_path = f"docs/{new_name}/{yaml_files[0].name}"
            return f"✅ Diretório renomeado: `{old_name}` → `{new_name}`\n📄 Arquivo YAML: `{new_yaml_path}`"
        else:
            return f"✅ Diretório renomeado: `{old_name}` → `{new_name}`"

    except Exception as e:
        logger.error(f"❌ Error renaming directory: {e}", exc_info=True)
        return f"❌ Erro ao renomear: {str(e)}"


@tool
def rename_proposal_yaml(directory: str, new_filename: str) -> str:
    """
    Rename the YAML file within a proposal directory.

    Args:
        directory: Proposal directory (e.g., "2026-01-client-project")
        new_filename: New YAML filename (e.g., "proposta-client-project.yml")

    Returns:
        str: Confirmation message or error
    """
    # TODO: Implement YAML rename with validation
    logger.info(f"📝 rename_proposal_yaml({directory}, {new_filename}) - TODO")
    return "TODO: Implementar renomeação de YAML"


@tool
def validate_proposal_structure(directory: str) -> str:
    """
    Validate the structure and integrity of a proposal directory.

    ⚠️  ONLY call this when user EXPLICITLY asks to validate a proposal!
    DO NOT call this tool when listing proposals - it's expensive and unnecessary.

    Checks:
    - YAML file exists and is valid
    - Referenced images exist
    - Directory naming follows convention
    - No orphaned files

    Args:
        directory: Proposal directory to validate (e.g., "docs/2026-01-client-project")

    Returns:
        str: Validation report with issues found
    """
    # TODO: Implement validation logic
    logger.info(f"✅ validate_proposal_structure({directory}) - TODO")
    return "TODO: Implementar validação de estrutura"


logger.info("⚠️  Cleanup tools loaded (stubs only - implementation pending)")
