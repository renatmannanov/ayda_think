"""
Tag Handler - Add tags to messages via /tag command
Usage: Reply to a message with /tag #one #two
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from storage.google_sheets import GoogleSheetsStorage
from .utils import get_user_spreadsheet


async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /tag command - add tags to replied message.
    Usage: Reply to a message with /tag #one #two

    1. Extract tags from command
    2. Get the replied message content from Google Sheets
    3. Append tags to content
    4. Update message text and Google Sheets
    5. Delete the /tag command message
    """
    message = update.message
    user_id = update.effective_user.id

    # Check if it's a reply
    if not message.reply_to_message:
        await message.reply_text("⚠️ Ответьте этой командой на сообщение, к которому хотите добавить теги.")
        return

    # Extract tags from command text
    command_text = message.text or ""
    tags = [word for word in command_text.split() if word.startswith('#')]

    if not tags:
        await message.reply_text("⚠️ Укажите теги после команды.\nПример: /tag #work #important")
        return

    # Get user's spreadsheet
    spreadsheet_id = get_user_spreadsheet(user_id)
    if not spreadsheet_id:
        await message.reply_text("⚠️ Вы еще не подключили таблицу. Нажмите /start для инструкции.")
        return

    replied_msg = message.reply_to_message
    replied_msg_id = replied_msg.message_id
    chat_id = message.chat_id

    # Get current content
    current_content = replied_msg.text or replied_msg.caption or ""

    # Append tags to content
    tags_string = " ".join(tags)
    new_content = f"{current_content}\n\n{tags_string}" if current_content else tags_string

    # Extract all tags from new content
    all_tags = [word for word in new_content.split() if word.startswith('#')]

    # Update in Google Sheets
    storage: GoogleSheetsStorage = context.bot_data['storage']
    try:
        await storage.update_note(spreadsheet_id, replied_msg_id, new_content, all_tags)
        logging.info(f"Added tags {tags} to message {replied_msg_id}")
    except Exception as e:
        logging.error(f"Error updating tags in sheet: {e}")
        await message.reply_text(f"❌ Ошибка при обновлении: {str(e)}")
        return

    # Try to edit the replied message (only works for bot's own messages)
    try:
        if replied_msg.text:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=replied_msg_id,
                text=new_content
            )
        elif replied_msg.caption:
            await context.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=replied_msg_id,
                caption=new_content
            )
        logging.info(f"Edited message {replied_msg_id} with new tags")
    except Exception as e:
        # Can't edit user's message - that's expected
        logging.info(f"Could not edit message (not bot's message): {e}")

    # Delete the /tag command message
    try:
        await message.delete()
        logging.info(f"Deleted /tag command message")
    except Exception as e:
        logging.warning(f"Could not delete /tag command: {e}")
