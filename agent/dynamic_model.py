"""
Dynamic model switching based on tool usage

This module allows the agent to use different models (Haiku vs Sonnet)
depending on which tools are being used, without using Teams.

Strategy:
- Haiku (fast, cheap): Basic operations (structure, read section, update field)
- Sonnet 4.5 (expensive, powerful): Full YAML operations (load, save entire proposal)
"""

import logging
from typing import Optional, Set
from agno.models.anthropic import Claude

logger = logging.getLogger(__name__)

# Tool categorization
EXPENSIVE_TOOLS = {
    'load_proposal_yaml',  # Loading entire YAML (~5000-10000 tokens)
    'save_proposal_yaml',  # Creating/saving full YAML proposals
}

CHEAP_TOOLS = {
    'get_proposal_structure',  # Only structure/outline
    'read_section_content',    # Single section content
    'update_proposal_field',   # Surgical field edits
    'list_existing_proposals_tool',  # List proposals
    'generate_image_dalle',    # Image generation (external API)
    'wait_for_user_image',     # Wait for user upload
    'add_user_image_to_yaml',  # Add image to YAML
    'commit_and_push_submodule',  # Git operations
    'delete_proposal',         # Delete operations
    'generate_pdf_from_yaml_tool',  # PDF generation (external)
}


def get_model_for_tools(tools_used: Optional[Set[str]] = None) -> Claude:
    """
    Get appropriate Claude model based on tools being used

    Args:
        tools_used: Set of tool names that will be/were used in this turn
                   If None, defaults to Sonnet 4.5

    Returns:
        Claude model instance (Haiku or Sonnet 4.5)
    """
    if tools_used is None:
        # No tool info - default to Sonnet for safety
        logger.info("🎯 No tool info - using Sonnet 4.5 (default)")
        return Claude(
            id="claude-sonnet-4-5",
            cache_system_prompt=True,
            betas=["extended-cache-ttl-2025-04-11"],
            extended_cache_time=True,
        )

    # Check if any expensive tool is being used
    uses_expensive = bool(tools_used & EXPENSIVE_TOOLS)

    if uses_expensive:
        logger.info(f"💎 Using Sonnet 4.5 for expensive tools: {tools_used & EXPENSIVE_TOOLS}")
        return Claude(
            id="claude-sonnet-4-5",
            cache_system_prompt=True,
            betas=["extended-cache-ttl-2025-04-11"],
            extended_cache_time=True,
        )
    else:
        logger.info(f"⚡ Using Haiku for cheap tools: {tools_used}")
        return Claude(
            id="claude-3-5-haiku-20241022",  # Haiku 3.5
            cache_system_prompt=True,
            betas=["extended-cache-ttl-2025-04-11"],
            extended_cache_time=True,
        )


def should_use_haiku(message: str) -> bool:
    """
    Heuristic to decide if we can use Haiku based on user message

    STRATEGY: "Haiku for Simple, Sonnet for Complex/Polish"
    - Use Haiku for simple operations (single edits, viewing, listing)
    - Use Sonnet for complex operations (creating proposals, multi-step edits, reasoning)
    - Use Sonnet for polish/review (quality-critical moments)

    This balances cost savings with quality and reliability.

    Args:
        message: User message

    Returns:
        True if message suggests using Haiku (simple operations)
        False if message requires Sonnet (complex/polish operations)
    """
    message_lower = message.lower()

    # 1. CRITICAL: Use Sonnet for polish/review requests
    polish_keywords = [
        'revisar',
        'revise',
        'revisada',
        'revisar proposta',
        'revisão',
        'polir',
        'polish',
        'polida',
        'bem pensada',
        'finalizar',
        'finalize',
        'finalizada',
        'versão final',
        'review',
        'revisar tudo',
        'revisar completa',
        'aprimorar',
        'melhorar',
        'melhorar a qualidade',
        'melhore',
        'melhorar redação',
        'aprimorar',
    ]

    for keyword in polish_keywords:
        if keyword in message_lower:
            logger.info(f"💎 Keyword '{keyword}' requires polish/review - using Sonnet for quality")
            return False

    # 2. Use Sonnet for CREATING new proposals (complex multi-step task)
    creation_keywords = [
        'criar proposta',
        'nova proposta',
        'create proposal',
        'new proposal',
        'fazer proposta',
        'fazer uma proposta',
        'montar proposta',
        'gerar proposta',
    ]

    for keyword in creation_keywords:
        if keyword in message_lower:
            logger.info(f"💎 Keyword '{keyword}' requires creation - using Sonnet for quality")
            return False

    # 3. Use Sonnet for COMPLEX multi-step operations
    complex_keywords = [
        'adicionar seção',
        'add section',
        'nova seção',
        'reorganizar',
        'reorganize',
        'reestruturar',
        'mover',
        'move',
        'duplicar',
        'duplicate',
    ]

    for keyword in complex_keywords:
        if keyword in message_lower:
            logger.info(f"💎 Keyword '{keyword}' requires complex reasoning - using Sonnet for reliability")
            return False

    # 4. Use Haiku for SIMPLE operations (viewing, single edits, listing)
    # Haiku is perfectly capable of:
    # - Listing proposals
    # - Viewing sections
    # - Single field edits ("mudar título", "atualizar imagem")
    # - Simple tool operations
    logger.info(f"⚡ Using Haiku for simple operation (fast & cheap)")
    return True


def estimate_cost_savings(haiku_tokens: int, sonnet_tokens: int) -> dict:
    """
    Estimate cost savings from using Haiku vs Sonnet

    Args:
        haiku_tokens: Number of tokens used with Haiku
        sonnet_tokens: Number of tokens that would have been used with Sonnet

    Returns:
        Dict with savings info
    """
    # Pricing (Dec 2024)
    # Haiku 3.5: $0.80/1M input, $4.00/1M output
    # Sonnet 4.5: $3.00/1M input, $15.00/1M output

    HAIKU_INPUT = 0.80
    HAIKU_OUTPUT = 4.00
    SONNET_INPUT = 3.00
    SONNET_OUTPUT = 15.00

    # Assume 70% input, 30% output (typical ratio)
    haiku_cost = (haiku_tokens * 0.7 / 1_000_000 * HAIKU_INPUT +
                  haiku_tokens * 0.3 / 1_000_000 * HAIKU_OUTPUT)

    sonnet_cost = (sonnet_tokens * 0.7 / 1_000_000 * SONNET_INPUT +
                   sonnet_tokens * 0.3 / 1_000_000 * SONNET_OUTPUT)

    savings = sonnet_cost - haiku_cost
    savings_pct = (savings / sonnet_cost * 100) if sonnet_cost > 0 else 0

    return {
        'haiku_cost': haiku_cost,
        'sonnet_cost': sonnet_cost,
        'savings': savings,
        'savings_pct': savings_pct,
    }
