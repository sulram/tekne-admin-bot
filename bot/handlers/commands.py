"""
Command handlers for bot commands (/hello, /help, /cost, /reset*)
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.auth import check_auth
from bot.session import clear_session
from core.cost_tracking import get_cost_stats, reset_cost_tracking
from agent.agent import reset_agent_session
from agent.tools import list_existing_proposals, generate_pdf_from_yaml  # Simple functions (not @tool decorated)
from config import SUBMODULE_PATH

logger = logging.getLogger(__name__)


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the user"""
    user = update.effective_user
    await update.message.reply_text(
        f'Hello {user.first_name}!\n'
        f'Your user ID: `{user.id}`'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message with available commands organized by category"""
    help_text = """
📖 *Comandos Disponíveis*

*PRINCIPAIS (mostrados no menu)*
/proposal - ✨ Criar nova proposta comercial
/reset - 🔄 Nova sessão (limpar conversa e custos)
/help - 📖 Mostrar esta mensagem

*GERAÇÃO DE PDF (sem gastar tokens)*
/list - 📋 Listar propostas com links para gerar PDF
/pdf - 📄 Gerar PDF diretamente (bypass agent)

*OUTROS COMANDOS*
/cost - 💰 Ver estatísticas de uso da API
/hello - 👋 Teste básico de conexão

*COMANDOS AVANÇADOS*
/resetdaily - 🗓️ Resetar apenas custos diários
/resetall - ⚠️ Resetar TODOS os custos (total + diário + sessões)

📝 *OUTRAS FUNCIONALIDADES*
• Envie mensagens de voz ou áudio → transcrevo para você!
• Envie mensagens de texto → converso sobre propostas
• Envie imagens → adiciono às propostas
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


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
        message += "=" * 10 + "\n\n"

        # Total
        message += f"💵 *TOTAL (all time)*\n"
        message += f"   Custo: `${total['cost']:.4f}`\n"
        total_tokens = total['input_tokens'] + total['output_tokens']
        message += f"   Tokens: `{total['input_tokens']:,}` in + `{total['output_tokens']:,}` out = `{total_tokens:,}`\n"

        # Cache stats (if available)
        cache_read = total.get('cache_read_tokens', 0)
        cache_write = total.get('cache_creation_tokens', 0)
        if cache_read > 0 or cache_write > 0:
            message += f"   🔄 Cache: `{cache_read:,}` read + `{cache_write:,}` write\n"
        message += "\n"

        # Today
        today = datetime.now().strftime('%Y-%m-%d')
        if today in daily:
            d = daily[today]
            message += f"📅 *HOJE* ({today})\n"
            message += f"   Custo: `${d['cost']:.4f}`\n"
            message += f"   Requisições: `{d['requests']}`\n"
            message += f"   Tokens: `{d['input_tokens']:,}` in + `{d['output_tokens']:,}` out\n"

            # Cache stats for today
            d_cache_read = d.get('cache_read_tokens', 0)
            d_cache_write = d.get('cache_creation_tokens', 0)
            if d_cache_read > 0 or d_cache_write > 0:
                message += f"   🔄 Cache: `{d_cache_read:,}` read + `{d_cache_write:,}` write\n"
            message += "\n"

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
            message += f"   Tokens: `{s['input_tokens']:,}` in + `{s['output_tokens']:,}` out\n"

            # Cache stats for session
            s_cache_read = s.get('cache_read_tokens', 0)
            s_cache_write = s.get('cache_creation_tokens', 0)
            if s_cache_read > 0 or s_cache_write > 0:
                message += f"   🔄 Cache: `{s_cache_read:,}` read + `{s_cache_write:,}` write\n"
            message += "\n"

        # Last update
        if stats['last_update']:
            last_update_str = stats['last_update'][:19]  # Remove microseconds
            message += f"🕐 Última atualização: `{last_update_str}`\n"

        message += "=" * 10

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error getting cost stats: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao obter estatísticas: {str(e)}")


async def reset_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset proposal generation session and cost tracking for this user"""
    user_id = update.effective_user.id
    session_id = f"user_{user_id}"

    # Clear user session
    clear_session(user_id)

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


async def list_proposals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent proposals with clickable /pdf commands"""
    user_id = await check_auth(update, "list command")
    if user_id is None:
        return

    try:
        # Get list of proposals (returns formatted string)
        proposals_text = list_existing_proposals(limit=10)

        # Parse the text to extract proposal numbers and paths
        # Format: "1. 📄 docs/yyyy-mm-folder/proposta-name.yml"
        lines = proposals_text.split('\n')
        message = "📋 *Propostas Recentes*\n\n"

        # Build inline keyboard buttons
        # Store paths in context for callback lookup (callback_data limited to 64 bytes)
        keyboard = []
        proposal_paths = []

        for line in lines:
            if line.strip() and '📄' in line:
                # Extract the path from the line
                # Example: "1. 📄 docs/2026-01-coca-cola/proposta-vr-bubble-experience.yml"
                parts = line.split('📄')
                if len(parts) >= 2:
                    number = parts[0].strip().rstrip('.')
                    path = parts[1].strip()

                    # Extract folder name for display
                    # docs/2026-01-coca-cola/proposta-vr-bubble-experience.yml -> 2026-01-coca-cola
                    folder = path.split('/')[1] if '/' in path else path

                    # Extract filename without extension for button label
                    filename = path.split('/')[-1].replace('.yml', '').replace('proposta-', '')

                    message += f"{number}. {folder}\n"

                    # Store path for callback lookup
                    proposal_paths.append(f"docs/{path}")
                    idx = len(proposal_paths) - 1

                    # Add button with short index (fits in 64 bytes)
                    keyboard.append([
                        InlineKeyboardButton(
                            f"📄 {filename}",
                            callback_data=f"pdf:{idx}"
                        )
                    ])

        # Store paths in user_data for callback handler
        context.user_data['proposal_paths'] = proposal_paths

        message += "\n💡 _Clique em um botão para gerar o PDF sem usar o agente_"

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        logger.info(f"User {user_id} listed proposals")

    except Exception as e:
        logger.error(f"Error listing proposals: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao listar propostas: {str(e)}")


async def handle_pdf_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle PDF generation from inline keyboard button"""
    query = update.callback_query
    await query.answer()  # Acknowledge the button click

    user_id = update.effective_user.id

    # Extract index from callback_data (format: "pdf:0", "pdf:1", etc)
    if not query.data or not query.data.startswith("pdf:"):
        await query.edit_message_text("❌ Erro: dados inválidos")
        return

    try:
        idx = int(query.data[4:])  # Remove "pdf:" prefix and convert to int
    except ValueError:
        await query.edit_message_text("❌ Erro: índice inválido")
        return

    # Get path from stored user_data
    proposal_paths = context.user_data.get('proposal_paths', [])
    if idx < 0 or idx >= len(proposal_paths):
        await query.edit_message_text("❌ Erro: proposta não encontrada. Use /list novamente.")
        return

    yaml_path = proposal_paths[idx]

    try:
        # Update message to show generating status
        await query.edit_message_text(f"🔨 Gerando PDF...\n`{yaml_path}`", parse_mode='Markdown')

        # Generate PDF directly (bypass agent)
        # yaml_path already includes "docs/" prefix from callback_data
        logger.info(f"User {user_id} generating PDF via button: {yaml_path}")
        result = generate_pdf_from_yaml(yaml_path)

        # Check if successful
        if "PDF gerado com sucesso" in result:
            # Extract PDF path from result
            # yaml_path already includes docs/ prefix
            pdf_path_relative = result.split(": ")[-1] if ": " in result else yaml_path.replace('.yml', '.pdf')
            pdf_full_path = SUBMODULE_PATH / pdf_path_relative

            if pdf_full_path.exists():
                # Send the PDF
                logger.info(f"Sending PDF: {pdf_full_path}")
                with open(pdf_full_path, 'rb') as pdf_file:
                    await query.message.reply_document(
                        document=pdf_file,
                        filename=pdf_full_path.name,
                        caption=f"✅ PDF gerado com sucesso!"
                    )

                # Update original message
                await query.edit_message_text(
                    f"✅ PDF gerado com sucesso!\n`{yaml_path}`",
                    parse_mode='Markdown'
                )
                logger.info(f"PDF sent successfully to user {user_id}")
            else:
                await query.edit_message_text(f"⚠️ PDF gerado mas não encontrado: {pdf_path_relative}")
        else:
            # Error generating PDF
            await query.edit_message_text(f"❌ {result}")

    except Exception as e:
        logger.error(f"Error in handle_pdf_button: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Erro ao gerar PDF: {str(e)}")


async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate PDF directly without using the agent (for testing)"""
    user_id = await check_auth(update, "pdf command")
    if user_id is None:
        return

    # Get the YAML path from command arguments
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "❌ Uso: `/pdf <caminho-yaml>`\n\n"
            "Exemplo: `/pdf docs/2026-01-coca-cola/proposta-vr-bubble-experience.yml`\n\n"
            "Use `/list` para ver as propostas disponíveis.",
            parse_mode='Markdown'
        )
        return

    yaml_path = ' '.join(context.args)  # Join in case path has spaces

    try:
        # Send status message
        status_msg = await update.message.reply_text("🔨 Gerando PDF...")

        # Generate PDF directly (bypass agent)
        logger.info(f"User {user_id} generating PDF directly: {yaml_path}")
        result = generate_pdf_from_yaml(yaml_path)

        # Delete status message
        await status_msg.delete()

        # Check if successful
        if "PDF gerado com sucesso" in result:
            # Extract PDF path from result
            # Format: "PDF gerado com sucesso: docs/2026-01-coca-cola/2026-01-01-vr-bubble-experience.pdf"
            pdf_path_relative = result.split(": ")[-1] if ": " in result else yaml_path.replace('.yml', '.pdf')
            pdf_full_path = SUBMODULE_PATH / pdf_path_relative

            if pdf_full_path.exists():
                # Send the PDF
                logger.info(f"Sending PDF: {pdf_full_path}")
                with open(pdf_full_path, 'rb') as pdf_file:
                    await update.message.reply_document(
                        document=pdf_file,
                        filename=pdf_full_path.name,
                        caption=f"✅ PDF gerado com sucesso!"
                    )
                logger.info(f"PDF sent successfully to user {user_id}")
            else:
                await update.message.reply_text(f"⚠️ PDF gerado mas não encontrado: {pdf_path_relative}")
        else:
            # Error generating PDF
            await update.message.reply_text(f"❌ {result}")

    except Exception as e:
        logger.error(f"Error in pdf_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao gerar PDF: {str(e)}")
