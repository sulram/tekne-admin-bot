"""
Bot utility functions for message handling
"""

import asyncio
from telegram import Update
from config import MAX_MESSAGE_LENGTH


async def send_long_message(update: Update, message: str, status_msg=None) -> None:
    """Send long messages by splitting them into chunks"""
    if len(message) <= MAX_MESSAGE_LENGTH:
        if status_msg:
            await status_msg.edit_text(message)
        else:
            await update.message.reply_text(message)
        return

    # Delete status message if exists
    if status_msg:
        await status_msg.delete()

    # Split message into chunks
    chunks = []
    while message:
        if len(message) <= MAX_MESSAGE_LENGTH:
            chunks.append(message)
            break

        # Find a good break point (newline, period, or space)
        split_at = MAX_MESSAGE_LENGTH
        for sep in ['\n\n', '\n', '. ', ' ']:
            pos = message[:MAX_MESSAGE_LENGTH].rfind(sep)
            if pos > MAX_MESSAGE_LENGTH * 0.7:  # Don't split too early
                split_at = pos + len(sep)
                break

        chunks.append(message[:split_at])
        message = message[split_at:]

    # Send chunks
    for i, chunk in enumerate(chunks):
        if i == 0:
            await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(f"(continuação {i+1}):\n\n{chunk}")


async def show_progress(status_msg) -> None:
    """Show animated progress indicator while agent is processing"""
    spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    messages = [
        "💭 Processando",
        "🤔 Analisando sua solicitação",
        "📝 Preparando resposta",
        "🧠 Pensando",
        "⚙️ Trabalhando nisso",
    ]

    spinner_idx = 0
    message_idx = 0
    elapsed = 0

    try:
        while True:
            # Update message every 3 seconds, spinner every 0.3s
            if elapsed % 10 == 0:  # Every 3 seconds
                current_message = messages[message_idx % len(messages)]
                message_idx += 1

            spinner = spinners[spinner_idx % len(spinners)]

            try:
                await status_msg.edit_text(f"{spinner} {current_message}...")
            except Exception:
                # Ignore errors if message hasn't changed or rate limited
                pass

            await asyncio.sleep(0.3)
            spinner_idx += 1
            elapsed += 1

    except asyncio.CancelledError:
        # Task was cancelled, processing is done
        pass
