"""
CopyMaster Agent - High-quality proposal creation and restructuring

Specializes in:
- Creating new proposals from scratch
- Restructuring and reorganizing content
- Improving writing quality
- Complex multi-section edits
"""

import logging
from pathlib import Path
from agno.agent import Agent
from agno.models.anthropic import Claude

from agent.agent import load_claude_instructions
from agent.tools import (
    save_proposal_yaml,
    load_proposal_yaml,
    update_proposal_field,
    get_proposal_structure,
    read_section_content,
    delete_proposal,
    generate_pdf_from_yaml_tool,
    generate_image_dalle,
    wait_for_user_image,
    add_user_image_to_yaml,
    commit_and_push_submodule,
)

logger = logging.getLogger(__name__)


def _load_skill_instructions() -> str:
    """Load skill.md from submodule if available"""
    skill_path = Path("submodules/tekne-proposals/.claude/skills/proposal-generator/skill.md")

    if skill_path.exists():
        try:
            skill_content = skill_path.read_text(encoding='utf-8')
            logger.info(f"✅ Loaded skill.md: {len(skill_content)} chars")
            return skill_content
        except Exception as e:
            logger.warning(f"⚠️ Failed to load skill.md: {e}")
            return ""
    else:
        logger.warning(f"⚠️ skill.md not found at {skill_path}")
        return ""


# Build CopyMaster instructions
COPYMASTER_INSTRUCTIONS = f"""
{load_claude_instructions()}

{_load_skill_instructions()}

---

## COPYMASTER SPECIALIZATION

You are CopyMaster - the creative specialist for proposal content generation and improvement.

**IMPORTANT: You are called AFTER Manager prepares the project context and briefing.**

**When to use your skills:**
- Generating proposal content from Manager's briefing
- Restructuring entire sections
- Improving writing quality and tone
- Merging or splitting content
- Major rewrites and expansions

**Your workflow:**
1. For new proposals: Receive briefing from Manager → Use schema to create comprehensive YAML
2. For complex edits: Load full proposal, restructure, save
3. For quality improvements: Enhance tone, clarity, persuasiveness
4. Always: Save → Generate PDF → Commit

**Response style:**
- Concise (2-3 lines max)
- Past tense: "Criei a proposta" not "Vou criar"
- Telegram markdown: *bold*, _italic_, `code`
- Professional but warm tone
"""


# Create CopyMaster agent
copymaster_agent = Agent(
    name="CopyMaster",
    model=Claude(
        id="claude-sonnet-4-5",
        cache_system_prompt=True,      # ✅ Agno native caching
        extended_cache_time=True,      # ✅ 1-hour TTL
        betas=["extended-cache-ttl-2025-04-11"],  # ✅ Anthropic beta
    ),
    description="ONLY writes final proposal content AFTER receiving complete briefing from Manager. DO NOT call for new proposals - Manager must prepare context first. Specializes in: finalizing proposals from briefing, restructuring existing content, improving writing quality, enhancing persuasiveness.",
    tools=[
        save_proposal_yaml,
        load_proposal_yaml,
        update_proposal_field,
        get_proposal_structure,
        read_section_content,
        delete_proposal,
        generate_pdf_from_yaml_tool,
        generate_image_dalle,
        wait_for_user_image,
        add_user_image_to_yaml,
        commit_and_push_submodule,
        # list_existing_proposals_tool removed - Leader handles this
    ],
    instructions=COPYMASTER_INSTRUCTIONS,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=False,  # Telegram uses different markdown
)


logger.info("✅ CopyMaster agent initialized with cache_system_prompt=True")
