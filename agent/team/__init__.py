"""
Tekne Proposal Team - Multi-agent system

Uses Agno Team with internal leader for intelligent delegation to specialists:
- Manager: Administrative operations, listing, cleanup (Haiku 3.5)
- CopyMaster: Creative, structural, complex tasks (Sonnet 4.5)
- Reviewer: Fast, surgical, atomic edits (Haiku 3.5)

Team's internal leader delegates based on agent descriptions and user intent.
"""

import logging
import time
from agno.team import Team
from agno.db.in_memory import InMemoryDb
from agno.models.anthropic import Claude

from agent.team.manager import manager_agent
from agent.team.copymaster import copymaster_agent
from agent.team.reviewer import reviewer_agent
from config import REDIS_URL
from core.callbacks import send_status, set_current_session
from core.cost_tracking import track_cost
from core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


# No longer using custom log filter - we use stream_events instead
# This is cleaner and doesn't require DEBUG mode


def get_team_db():
    """Get database for team - Redis if available, InMemory as fallback"""
    redis_client = get_redis_client()

    if redis_client is not None:
        try:
            from agno.db.redis import RedisDb
            logger.info("✅ Using RedisDb for team memory")
            return RedisDb(
                db_url=REDIS_URL,
                session_table="agent_sessions",  # Same table as single agent for compatibility
            )
        except ImportError:
            logger.warning("⚠️  Redis module not available, using InMemoryDb (sessions won't persist)")
            return InMemoryDb()
    else:
        logger.warning("⚠️  Redis unavailable, using InMemoryDb (sessions won't persist)")
        return InMemoryDb()


# Create Team with internal team leader
# Team automatically creates a leader that delegates to members based on their descriptions
# Members should have clear `name`, `role`, and `description` for proper routing
proposal_team = Team(
    members=[manager_agent, copymaster_agent, reviewer_agent],  # Specialists only (no custom leader)
    name="Proposal Team",
    description="Multi-agent system for managing commercial proposals with intelligent delegation",

    # ✅ CRITICAL: Force Team leader to use Haiku 3.5 (NOT OpenAI default!)
    model=Claude(
        id="claude-3-5-haiku-20241022",  # Same as Manager/Reviewer for consistency
        max_tokens=4096,  # Team leader needs space for routing decisions
    ),

    db=get_team_db(),
    # Delegation configuration (Agno v2)
    respond_directly=True,  # ✅ Members respond directly to user (no synthesis)
    determine_input_for_members=True,  # Team leader transforms input before delegation
    delegate_to_all_members=False,  # Selective delegation (not all at once)
    store_member_responses=True,  # ✅ CRITICAL: Store member responses for logging
    show_members_responses=False,  # Don't show verbose member logs

    # ✅ No streaming - cleaner logs, faster responses
    debug_mode=False,  # Disabled for clean logs
    debug_level=1,  # Not used
    store_events=False,  # Don't store events in database
    stream_events=False,  # Disabled - token-by-token streaming floods logs
)


def run_team(message: str, session_id: str = "default") -> str:
    """
    Run team with given message and session

    Args:
        message: User message
        session_id: Session ID for conversation tracking

    Returns:
        Team response text
    """
    logger.info(f"🤖 [Session {session_id}] User message:\n{message}")

    # Bind session to current thread (for ThreadLocal callback routing)
    set_current_session(session_id)

    # Send initial status to Telegram
    try:
        send_status("🧠 Analisando sua solicitação...")
    except Exception as e:
        logger.debug(f"Could not send initial status: {e}")

    try:
        # Time the API call
        start_time = time.time()
        response = proposal_team.run(message, session_id=session_id, stream=False)
        elapsed_time = time.time() - start_time
    finally:
        # Clear session binding
        set_current_session(None)

    # Log delegation decision and send to Telegram
    if hasattr(response, 'member_responses') and response.member_responses:
        delegated_to = [m.agent_name for m in response.member_responses if hasattr(m, 'agent_name')]
        agent_names = ', '.join(delegated_to)
        logger.info(f"🎯 Delegated to: {agent_names}")
        # Agent info will be sent after processing completes
    else:
        logger.info("🎯 Team leader handled directly (no delegation)")
        # Agent info will be sent after processing completes

    # Detect which agents were used and which tools they called
    agents_used = set()
    tools_used = []

    # Extract agents and tools from member_responses (RunOutput objects)
    if hasattr(response, 'member_responses') and response.member_responses:
        for member_run in response.member_responses:
            # Get agent name (RunOutput has agent_name attribute)
            if hasattr(member_run, 'agent_name') and member_run.agent_name:
                agents_used.add(member_run.agent_name)

                # Extract tools from this member's ToolExecution objects
                if hasattr(member_run, 'tools') and member_run.tools:
                    for tool_exec in member_run.tools:
                        tool_name = tool_exec.tool_name if hasattr(tool_exec, 'tool_name') else str(tool_exec)
                        tools_used.append(tool_name)

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

        # Simplified cost calculation (approximation)
        # TODO: More precise calculation per agent in future
        from config import CLAUDE_INPUT_PRICE_PER_1M, CLAUDE_OUTPUT_PRICE_PER_1M

        base_input_cost = (input_tokens / 1_000_000) * CLAUDE_INPUT_PRICE_PER_1M
        cache_write_cost = (cache_creation_tokens / 1_000_000) * (CLAUDE_INPUT_PRICE_PER_1M * 2.0)
        cache_read_cost = (cache_read_tokens / 1_000_000) * (CLAUDE_INPUT_PRICE_PER_1M * 0.1)
        output_cost = (output_tokens / 1_000_000) * CLAUDE_OUTPUT_PRICE_PER_1M

        total_cost = base_input_cost + cache_write_cost + cache_read_cost + output_cost

        # Concise token/cost log
        cache_info = ""
        if cache_read_tokens > 0:
            cache_info = f" | Cache: {cache_read_tokens:,} read"
        logger.info(f"💰 {input_tokens:,} in + {output_tokens:,} out = ${total_cost:.4f}{cache_info}")

        # Track cumulative cost
        cost_info = track_cost(input_tokens, output_tokens, total_cost, session_id,
                              cache_read_tokens, cache_creation_tokens)

    # Log execution summary with agent name
    tools_str = ', '.join(tools_used) if tools_used else 'None'
    agent_str = ', '.join(agents_used) if agents_used else 'Team Leader'
    logger.info(f"✅ {elapsed_time:.1f}s | Agent: {agent_str} | Tools: {tools_str}")

    # Send agent + tools info to Telegram
    try:
        if tools_str != 'None':
            send_status(f"🤖 *Agente:* {agent_str}\n🔧 *Ferramentas:* {tools_str}")
        else:
            send_status(f"🤖 *Agente:* {agent_str}")
    except Exception as e:
        logger.debug(f"Could not send agent info to Telegram: {e}")

    # Check if PDF was generated
    pdf_generated = 'generate_pdf_from_yaml' in tools_used or 'generate_pdf_from_yaml_tool' in tools_used

    # Check if agent modified proposal but didn't commit
    if 'save_proposal_yaml' in tools_used and 'commit_and_push_submodule' not in tools_used:
        logger.warning(f"⚠️  [Session {session_id}] Team saved YAML but did NOT commit to git!")
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

    # Return member responses directly when respond_directly=True
    if hasattr(response, 'member_responses') and response.member_responses:
        # Format: "AGENT_NAME:\n{response}"
        formatted_responses = []
        for member_run in response.member_responses:
            if hasattr(member_run, 'agent_name') and hasattr(member_run, 'content'):
                agent_name = member_run.agent_name.upper()
                content = str(member_run.content)
                formatted_responses.append(f"*{agent_name}:*\n{content}")

        if formatted_responses:
            final_response = "\n\n".join(formatted_responses)
            logger.info(f"📤 Telegram response ({len(final_response)} chars):\n{final_response}")
            return final_response

    # Fallback to team response if no member responses
    if response and hasattr(response, 'content') and response.content:
        return response.content

    # Last resort: return a generic success message
    logger.warning("⚠️ No response content found, using fallback message")
    return "✅ Operação concluída com sucesso."


logger.info("✅ Proposal Team initialized (Agno internal leader)")
logger.info(f"   Team Leader: Haiku 3.5 (delegation routing)")
logger.info(f"   Specialists: Manager (Haiku 3.5), CopyMaster (Sonnet 4.5), Reviewer (Haiku 3.5)")
