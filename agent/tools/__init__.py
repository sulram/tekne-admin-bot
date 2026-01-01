"""
All agent tools exported for easy import

Note: Functions ending in _tool are @tool decorated for agent use.
Functions without _tool suffix are simple functions for direct use (bot commands, etc).
"""

# Simple functions (non-decorated, for bot commands)
from .proposal import (
    save_proposal_yaml,
    load_proposal_yaml,
    list_existing_proposals,  # Simple function
    update_proposal_field,
    get_proposal_structure,
    read_section_content
)
from .pdf import generate_pdf_from_yaml  # Simple function
from .image import generate_image_dalle, wait_for_user_image, add_user_image_to_yaml
from .git import commit_and_push_submodule

# Agent tools (@tool decorated, for agent use)
from .proposal import list_existing_proposals_tool
from .pdf import generate_pdf_from_yaml_tool

__all__ = [
    # Proposal tools (simple functions)
    'save_proposal_yaml',
    'load_proposal_yaml',
    'list_existing_proposals',
    'update_proposal_field',
    'get_proposal_structure',
    'read_section_content',

    # PDF tools (simple function)
    'generate_pdf_from_yaml',

    # Image tools
    'generate_image_dalle',
    'wait_for_user_image',
    'add_user_image_to_yaml',

    # Git tools
    'commit_and_push_submodule',

    # Agent tools (@tool decorated)
    'list_existing_proposals_tool',
    'generate_pdf_from_yaml_tool',
]
