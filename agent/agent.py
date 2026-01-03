"""
Tekne Proposal Generator Agent
Uses Agno with Claude to create commercial proposals following CLAUDE.md rules
"""

import logging
import os
import time
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.db.in_memory import InMemoryDb
from agno.db.redis import RedisDb

from config import CLAUDE_MD_PATH, CLAUDE_INPUT_PRICE_PER_1M, CLAUDE_OUTPUT_PRICE_PER_1M, REDIS_URL
from core.callbacks import send_status, set_current_session
from core.cost_tracking import track_cost
from core.redis_client import get_redis_client
from agent.tools import (
    save_proposal_yaml,
    load_proposal_yaml,
    list_existing_proposals_tool,  # @tool decorated version for agent
    update_proposal_field,
    get_proposal_structure,
    read_section_content,
    delete_proposal,
    generate_pdf_from_yaml_tool,  # @tool decorated version for agent
    generate_image_dalle,
    wait_for_user_image,
    add_user_image_to_yaml,
    commit_and_push_submodule,
)

logger = logging.getLogger(__name__)

# Cache for CLAUDE.md instructions (loaded once at startup)
_cached_instructions = None


def load_claude_instructions() -> str:
    """Load CLAUDE.md as agent instructions (cached after first load)"""
    global _cached_instructions

    # Return cached version if available
    if _cached_instructions is not None:
        logger.info(f"Using cached instructions ({len(_cached_instructions)} chars)")
        return _cached_instructions

    base_instructions = ""

    if CLAUDE_MD_PATH.exists():
        full_text = CLAUDE_MD_PATH.read_text()

        # Extract only schema/rules (stop before verbose examples)
        # Keep everything up to "## EXAMPLE PROMPT → YAML" section
        if "## EXAMPLE PROMPT → YAML" in full_text:
            base_instructions = full_text.split("## EXAMPLE PROMPT → YAML")[0]
            logger.info(f"Loaded CLAUDE.md schema (trimmed examples): {len(base_instructions)} chars")
        else:
            base_instructions = full_text
            logger.info(f"Loaded full CLAUDE.md: {len(base_instructions)} chars")
    else:
        base_instructions = "Generate proposals in YAML format for Tekne Studio."

    # Add bot-specific workflow rules (minimal - tools explain themselves via docstrings)
    bot_instructions = """

---

## BOT WORKFLOW RULES

**After ANY proposal edit/creation:**
1. Save YAML → Ask user if they want PDF generated → Generate PDF (only if user confirms) → Commit (in that order)
2. Commit message should describe the change clearly
3. **CRITICAL:** Always ask "Quer que eu gere o PDF agora?" after YAML edits - NEVER auto-generate PDF

**Token optimization (critical):**
- Start with `get_proposal_structure()` to navigate
- Use `read_section_content(index)` for single section context
- Only use `load_proposal_yaml()` when you need to see/restructure entire proposal
- Always edit with `update_proposal_field()` (never rewrite full YAML)

**PDF regeneration without edits:**
- If user just wants PDF regenerated → call `generate_pdf_from_yaml()` directly
- Do NOT load/update YAML unnecessarily
- Do NOT commit (git may not be available in production)

**Response style:**
- Concise (2-3 lines max)
- Past tense: "Editei a proposta" not "Vou editar"
- Telegram markdown: *bold*, _italic_, `code`
- Bot sends PDF automatically - don't include path in response
"""

    # Cache the instructions for future use
    _cached_instructions = base_instructions + bot_instructions

    logger.info(f"Total cached instructions: {len(_cached_instructions)} chars (~{len(_cached_instructions)//4} tokens)")

    return _cached_instructions


def get_agent_db():
    """Get database for agent - Redis if available, InMemory as fallback"""
    redis_client = get_redis_client()

    if redis_client is not None:
        logger.info("✅ Using RedisDb for agent memory")
        return RedisDb(
            db_url=REDIS_URL,
            session_table="agent_sessions",  # Correct parameter name per Agno docs
        )
    else:
        logger.warning("⚠️  Redis unavailable, using InMemoryDb (sessions won't persist)")
        return InMemoryDb()


# Create the agent
proposal_agent = Agent(
    name="Tekne Proposal Generator",
    model=Claude(
        id="claude-sonnet-4-5",  # Sonnet 4.5 for better accuracy
        cache_system_prompt=True,  # Enable prompt caching for system instructions
        betas=["extended-cache-ttl-2025-04-11"],  # Extended cache TTL (1 hour)
        extended_cache_time=True,  # Use 1-hour cache instead of 5-min
    ),
    db=get_agent_db(),  # Redis for persistence, InMemory as fallback
    instructions=load_claude_instructions(),
    tools=[
        save_proposal_yaml,
        update_proposal_field,
        get_proposal_structure,
        read_section_content,
        delete_proposal,
        generate_pdf_from_yaml_tool,  # Agent uses @tool decorated version
        generate_image_dalle,
        wait_for_user_image,
        add_user_image_to_yaml,
        commit_and_push_submodule,
        list_existing_proposals_tool,  # Agent uses @tool decorated version
        load_proposal_yaml,
    ],
    add_history_to_context=True,
    num_history_runs=5,  # Only keep last 5 runs to save tokens
    markdown=False,  # Disable markdown - Telegram uses different format
)


def get_agent_response(message: str, session_id: str = "default") -> str:
    """
    Get response from proposal agent

    Args:
        message: User message
        session_id: Session ID for conversation tracking

    Returns:
        Agent response text
    """
    logger.info(f"[Session {session_id}] User message: {message[:100]}...")

    # Bind session to current thread (for ThreadLocal callback routing)
    set_current_session(session_id)

    try:
        # Time the API call
        start_time = time.time()
        response = proposal_agent.run(message, session_id=session_id, stream=False)
        elapsed_time = time.time() - start_time
    finally:
        # Clear session binding
        set_current_session(None)

    logger.info(f"⏱️  Claude API response time: {elapsed_time:.2f} seconds")
    logger.info(f"[Session {session_id}] Agent response length: {len(response.content)} chars")

    # Log token usage and cost
    cost_info = None
    pdf_generated = False
    if hasattr(response, 'metrics') and response.metrics:
        # Metrics is an object, not a dict - use attribute access
        input_tokens = getattr(response.metrics, 'input_tokens', 0)
        output_tokens = getattr(response.metrics, 'output_tokens', 0)

        # Prompt caching metrics (Agno exposes these from Anthropic API)
        cache_read_tokens = getattr(response.metrics, 'cache_read_tokens', 0)
        cache_creation_tokens = getattr(response.metrics, 'cache_write_tokens', 0)

        total_tokens = input_tokens + output_tokens

        # Claude Sonnet 4.5 pricing
        # Base input tokens (not cached)
        base_input_cost = (input_tokens / 1_000_000) * CLAUDE_INPUT_PRICE_PER_1M
        # Cache creation (1-hour TTL = 2x base price)
        cache_write_cost = (cache_creation_tokens / 1_000_000) * (CLAUDE_INPUT_PRICE_PER_1M * 2.0)
        # Cache reads (0.1x base price - 90% savings!)
        cache_read_cost = (cache_read_tokens / 1_000_000) * (CLAUDE_INPUT_PRICE_PER_1M * 0.1)
        # Output tokens (no cache)
        output_cost = (output_tokens / 1_000_000) * CLAUDE_OUTPUT_PRICE_PER_1M

        total_cost = base_input_cost + cache_write_cost + cache_read_cost + output_cost

        # Log token breakdown
        logger.info(f"💰 Token usage: {input_tokens:,} in + {output_tokens:,} out = {total_tokens:,} total")
        if cache_read_tokens > 0 or cache_creation_tokens > 0:
            logger.info(f"🔄 Cache: {cache_read_tokens:,} read (90% savings!) + {cache_creation_tokens:,} write")
            cache_savings = (cache_read_tokens / 1_000_000) * CLAUDE_INPUT_PRICE_PER_1M * 0.9
            logger.info(f"💚 Cache savings: ${cache_savings:.4f} (vs non-cached)")

        logger.info(f"💵 Cost: ${base_input_cost:.4f} base + ${cache_write_cost:.4f} write + ${cache_read_cost:.4f} read + ${output_cost:.4f} out = ${total_cost:.4f} total")

        # Track cumulative cost
        cost_info = track_cost(input_tokens, output_tokens, total_cost, session_id,
                              cache_read_tokens, cache_creation_tokens)

    # Log if tools were used and check for missing commit
    tools_used = []
    if hasattr(response, 'messages'):
        for msg in response.messages:
            if hasattr(msg, 'role') and msg.role == 'assistant':
                if hasattr(msg, 'content') and msg.content is not None:
                    for block in msg.content:
                        if hasattr(block, 'type') and block.type == 'tool_use':
                            tools_used.append(block.name)
                            logger.info(f"[Session {session_id}] Tool used: {block.name}")

    # Check if PDF was generated
    pdf_generated = 'generate_pdf_from_yaml' in tools_used

    # Check if agent modified proposal but didn't commit
    if 'save_proposal_yaml' in tools_used and 'commit_and_push_submodule' not in tools_used:
        logger.warning(f"⚠️  [Session {session_id}] Agent saved YAML but did NOT commit to git!")
        send_status("⚠️ Aviso: Proposta salva mas não enviada ao repositório")

    # Send cost info if PDF was generated
    if pdf_generated and cost_info:
        cost_msg = (
            f"💰 _Custo desta requisição:_ `${cost_info['this_request']:.4f}`\n"
            f"📊 _Sessão:_ `${cost_info['session']:.4f}` | "
            f"_Hoje:_ `${cost_info['today']:.4f}` | "
            f"_Total:_ `${cost_info['total']:.4f}`"
        )
        send_status(cost_msg)

    return response.content


def reset_agent_session(session_id: str) -> bool:
    """Reset agent conversation history for a specific session

    Args:
        session_id: Session ID to reset

    Returns:
        bool: True if session was deleted, False otherwise
    """
    try:
        result = proposal_agent.db.delete_session(session_id)
        if result:
            logger.info(f"✅ Agent session {session_id} history cleared")
        else:
            logger.info(f"ℹ️ No session history found for {session_id}")
        return result
    except Exception as e:
        logger.error(f"❌ Error clearing agent session {session_id}: {e}")
        return False
