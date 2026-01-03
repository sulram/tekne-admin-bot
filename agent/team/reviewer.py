"""
Reviewer Agent - Fast, surgical edits to existing proposals

Specializes in:
- Quick typo fixes
- Updating specific fields (pricing, dates, names)
- Atomic, targeted changes
- Fast response times
"""

import logging
from agno.agent import Agent
from agno.models.anthropic import Claude

from agent.agent import load_claude_instructions
from agent.tools import (
    update_proposal_field,
    get_proposal_structure,
    read_section_content,
    generate_pdf_from_yaml_tool,
    commit_and_push_submodule,
)
from agent.tools.cleanup import rename_proposal_directory

logger = logging.getLogger(__name__)


REVIEWER_INSTRUCTIONS = f"""
{load_claude_instructions()}

---

## REVIEWER SPECIALIZATION

You are Reviewer - the speed specialist for quick, surgical edits.

**When to use your skills:**
- Fixing typos or grammar errors
- Updating prices, dates, client names
- Changing specific fields
- Quick corrections (single-field edits)

**Your workflow:**
1. Use `get_proposal_structure()` to locate the field
2. Use `read_section_content(index)` if you need to see current value
3. Use `update_proposal_field()` for atomic edits (NEVER load full YAML)
4. Always: Save → Generate PDF → Commit

**Optimization rules:**
- NEVER use `load_proposal_yaml()` (you don't need full context)
- ALWAYS use `update_proposal_field()` for edits
- Keep it fast and surgical

**Response style:**
- Ultra-concise (1-2 lines max)
- Past tense: "Corrigi o preço" not "Vou corrigir"
- Telegram markdown: *bold*, _italic_, `code`
- Direct and efficient tone
"""


# Create Reviewer agent
reviewer_agent = Agent(
    name="Reviewer",
    model=Claude(
        id="claude-3-5-haiku-20241022",  # Haiku for speed
        max_tokens=1024,  # Short responses
    ),
    description="Fast surgical edits to existing proposal content. Specializes in: changing dates, updating prices, fixing typos, correcting client names, single-field modifications, quick atomic edits. Use for ANY content change to existing proposals.",
    tools=[
        update_proposal_field,
        get_proposal_structure,
        read_section_content,
        generate_pdf_from_yaml_tool,
        commit_and_push_submodule,
        rename_proposal_directory,  # For changing dates (rename month folder)
    ],
    instructions=REVIEWER_INSTRUCTIONS,
    add_history_to_context=True,
    num_history_runs=3,  # Less history = faster
    markdown=False,
)


logger.info("✅ Reviewer agent initialized (Haiku for speed)")
