"""
Command handlers for bot commands (/hello, /help, /cost, /reset*)
"""

import logging
import threading
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers._shared import check_auth
from core.cost_tracking import get_cost_stats, reset_cost_tracking
from agent.agent import reset_agent_session

logger = logging.getLogger(__name__)

# Store user sessions (shared with messages.py)
user_sessions = {}
user_sessions_lock = threading.Lock()


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the user"""
    user = update.effective_user
    await update.message.reply_text(
        f'Hello {user.first_name}!\n'
        f'Your user ID: `{user.id}`'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message with available commands"""
    help_text = """
Available commands:
/hello - Greet the bot
/help - Show this help message
/cost - Show API usage statistics
/proposal - Start creating a new proposal
/reset - Reset current proposal conversation and your session costs
/resetdaily - Reset daily cost tracking
/resetall - Reset ALL cost tracking (requires confirmation)

You can also:
- Send voice messages or audio files, and I'll transcribe them for you!
- Send text messages to chat with the proposal generator
"""
    await update.message.reply_text(help_text)


async def cost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show API usage and cost statistics"""
    user_id = await check_auth(update, "cost command")
    if user_id is None:
        return

    try:
        stats = get_cost_stats()
        total = stats['total']
        daily = stats['daily']
        sessions = stats['sessions']

        # Build response message
        message = "📊 *Estatísticas de Uso da API*\n"
        message += "=" * 35 + "\n\n"

        # Total
        message += f"💵 *TOTAL (all time)*\n"
        message += f"   Custo: `${total['cost']:.4f}`\n"
        total_tokens = total['input_tokens'] + total['output_tokens']
        message += f"   Tokens: `{total['input_tokens']:,}` in + `{total['output_tokens']:,}` out = `{total_tokens:,}`\n\n"

        # Today
        today = datetime.now().strftime('%Y-%m-%d')
        if today in daily:
            d = daily[today]
            message += f"📅 *HOJE* ({today})\n"
            message += f"   Custo: `${d['cost']:.4f}`\n"
            message += f"   Requisições: `{d['requests']}`\n"
            message += f"   Tokens: `{d['input_tokens']:,}` in + `{d['output_tokens']:,}` out\n\n"

        # Recent days
        if len(daily) > 1:
            message += f"📆 *ÚLTIMOS 7 DIAS*\n"
            for day in sorted(daily.keys(), reverse=True)[:7]:
                d = daily[day]
                message += f"   `{day}`: ${d['cost']:.4f} ({d['requests']} req)\n"
            message += "\n"

        # User's session
        session_id = f"user_{user_id}"
        if session_id in sessions:
            s = sessions[session_id]
            message += f"👤 *SUA SESSÃO*\n"
            message += f"   Custo: `${s['cost']:.4f}`\n"
            message += f"   Requisições: `{s['requests']}`\n"
            message += f"   Tokens: `{s['input_tokens']:,}` in + `{s['output_tokens']:,}` out\n\n"

        # Last update
        if stats['last_update']:
            last_update_str = stats['last_update'][:19]  # Remove microseconds
            message += f"🕐 Última atualização: `{last_update_str}`\n"

        message += "=" * 35

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error getting cost stats: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao obter estatísticas: {str(e)}")


async def reset_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset proposal generation session and cost tracking for this user"""
    user_id = update.effective_user.id
    session_id = f"user_{user_id}"

    with user_sessions_lock:
        if user_id in user_sessions:
            del user_sessions[user_id]

    # Reset agent conversation history for this session
    reset_agent_session(session_id)

    # Reset cost tracking for this user's session
    reset_cost_tracking(scope="session", session_id=session_id)

    await update.message.reply_text("✅ Sessão e custos resetados! Use /proposal para começar uma nova proposta.")


async def reset_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset daily cost tracking"""
    user_id = await check_auth(update, "reset-daily command")
    if user_id is None:
        return

    # Reset daily cost tracking
    reset_cost_tracking(scope="daily")
    logger.info(f"User {user_id} reset daily cost tracking")
    await update.message.reply_text("✅ Custos diários resetados!")


async def reset_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset all cost tracking"""
    user_id = await check_auth(update, "resetall command")
    if user_id is None:
        return

    # Reset all cost tracking
    reset_cost_tracking(scope="all")
    logger.info(f"User {user_id} reset ALL cost tracking")
    await update.message.reply_text("✅ TODOS os custos foram resetados!\n\n⚠️ Todos os dados de custo (total, diário e sessões) foram apagados.")
