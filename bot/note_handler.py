from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes
from storage.google_sheets import GoogleSheetsStorage
from .utils import get_user_spreadsheet, extract_spreadsheet_id
from .forward_utils import (
    extract_forward_content, 
    get_forward_chat_id, 
    get_forward_username, 
    get_forward_chat_link
)
from .registration_handler import register_sheet
import logging

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle text messages (Registration or Notes).
    """
    user_id = update.effective_user.id
    msg_text = update.message.text or update.message.caption or ""
    
    # Check if it looks like a spreadsheet URL or ID (only for text messages, not forwards)
    is_forward = update.message.forward_origin is not None
    
    if not is_forward and msg_text:
        potential_id = extract_spreadsheet_id(msg_text)
        is_link = "docs.google.com/spreadsheets" in msg_text
        
        if is_link or (potential_id and len(potential_id) > 20 and " " not in msg_text):
            await register_sheet(update, context, potential_id)
            return
    
    # Otherwise, treat as note (including forwards)
    await save_note(update, context)

async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle edited messages - update the corresponding row in Google Sheets.
    """
    storage: GoogleSheetsStorage = context.bot_data['storage']
    user_id = update.effective_user.id
    spreadsheet_id = get_user_spreadsheet(user_id)
    
    if not spreadsheet_id:
        return  # Silently ignore if user hasn't registered
    
    edited_msg = update.edited_message
    message_id = edited_msg.message_id
    new_content = edited_msg.text or edited_msg.caption or ""
    new_tags = [word for word in new_content.split() if word.startswith('#')]
    
    try:
        await storage.update_note(spreadsheet_id, message_id, new_content, new_tags)
    except Exception as e:
        logging.error(f"Error handling edited message: {e}")

async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Save a note to Google Sheets.
    """
    storage: GoogleSheetsStorage = context.bot_data['storage']
    user_id = update.effective_user.id
    spreadsheet_id = get_user_spreadsheet(user_id)
    
    if not spreadsheet_id:
        await update.message.reply_text("⚠️ Вы еще не подключили таблицу. Нажмите /start для инструкции.")
        return

    is_forward = update.message.forward_origin is not None
    caption = update.message.caption or ""
    text = update.message.text or ""
    has_media = bool(update.message.photo or update.message.video or update.message.document or update.message.audio)
    
    logging.info(f"is_forward={is_forward}, has_media={has_media}, has_caption={bool(caption)}, has_text={bool(text)}")
    
    messages_to_save = []
    
    # Case 1: Media forward with caption (save both)
    if is_forward and has_media and caption:
        caption_tags = [word for word in caption.split() if word.startswith('#')]
        caption_note = {
            'message_id': update.message.message_id,
            'content': caption,
            'tags': caption_tags,
            'reply_to_message_id': None,
            'message_type': 'general',
            'source_chat_id': update.effective_chat.id,
            'source_chat_link': '',
            'telegram_username': ''
        }
        messages_to_save.append(caption_note)
        
        telegram_username = get_forward_username(update.message)
        forward_note = {
            'message_id': update.message.message_id,
            'content': '[Media]',
            'tags': [],
            'reply_to_message_id': None,
            'message_type': 'forwarded',
            'source_chat_id': get_forward_chat_id(update.message),
            'source_chat_link': get_forward_chat_link(update.message),
            'telegram_username': telegram_username
        }
        messages_to_save.append(forward_note)
    
    # Case 2: Pure forward (text or media without caption)
    elif is_forward:
        forward_content = extract_forward_content(update.message)
        telegram_username = get_forward_username(update.message)
        forward_note = {
            'message_id': update.message.message_id,
            'content': forward_content,
            'tags': [],
            'reply_to_message_id': update.message.reply_to_message.message_id if update.message.reply_to_message else None,
            'message_type': 'forwarded',
            'source_chat_id': get_forward_chat_id(update.message),
            'source_chat_link': get_forward_chat_link(update.message),
            'telegram_username': telegram_username
        }
        messages_to_save.append(forward_note)
    
    # Case 3: Regular message (not a forward)
    else:
        tags = [word for word in text.split() if word.startswith('#')]
        reply_to_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
        
        note_data = {
            'message_id': update.message.message_id,
            'content': text,
            'tags': tags,
            'reply_to_message_id': reply_to_id,
            'message_type': 'general',
            'source_chat_id': update.effective_chat.id,
            'source_chat_link': '',
            'telegram_username': ''
        }
        messages_to_save.append(note_data)
    
    # Save all messages
    try:
        logging.info(f"Saving {len(messages_to_save)} messages")
        for i, note in enumerate(messages_to_save):
            logging.info(f"Message {i+1}: type={note.get('message_type')}")
            await storage.save_note(spreadsheet_id, note)
        await update.message.set_reaction(reaction=ReactionTypeEmoji(emoji="✍️"))
    except Exception as e:
        logging.error(f"Error saving: {e}")
        await update.message.reply_text(f"❌ Ошибка при сохранении: {str(e)}")
