"""
Bot handlers - organized by domain

Exports:
- Command handlers: /hello, /help, /cost, /reset*
- Message handlers: text, audio, photo, proposal
"""

from bot.handlers.commands import (
    hello,
    help_command,
    cost_command,
    reset_proposal,
    reset_daily,
    reset_all,
    list_proposals,
    pdf_command,
    handle_pdf_button,
)

from bot.handlers.messages import (
    start_proposal,
    handle_text_message,
    handle_audio,
    handle_photo,
)

__all__ = [
    # Commands
    "hello",
    "help_command",
    "cost_command",
    "reset_proposal",
    "reset_daily",
    "reset_all",
    "list_proposals",
    "pdf_command",
    "handle_pdf_button",
    # Messages
    "start_proposal",
    "handle_text_message",
    "handle_audio",
    "handle_photo",
]
