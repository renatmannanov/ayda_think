from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from storage.google_sheets import GoogleSheetsStorage
from .utils import save_user, get_user_spreadsheet, extract_spreadsheet_id
import logging

# We will use a simple function-based approach for handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command.
    """
    storage: GoogleSheetsStorage = context.bot_data['storage']
    email = storage.get_service_account_email()
    
    text = (
        "👋 Привет! Я бот для сохранения заметок в Google Таблицы.\n\n"
        "**Как начать:**\n"
        "1. Создайте новую Google Таблицу.\n"
        f"2. Нажмите 'Настройки доступа' (Share) и добавьте этот email:\n`{email}`\n(дайте права Редактора)\n"
        "3. Пришлите мне ссылку на таблицу (или её ID).\n\n"
        "После этого все ваши сообщения будут сохраняться туда!"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

import time

# Rate limiting removed - Telegram sends forward+caption as 2 separate updates,
# and rate limiting was blocking the second one

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle text messages (Registration or Notes).
    """
    user_id = update.effective_user.id

    msg_text = update.message.text or update.message.caption or ""
    storage: GoogleSheetsStorage = context.bot_data['storage']
    
    # Check if it looks like a spreadsheet URL or ID (only for text messages, not forwards)
    is_forward = update.message.forward_origin is not None
    
    if not is_forward and msg_text:
        potential_id = extract_spreadsheet_id(msg_text)
        is_link = "docs.google.com/spreadsheets" in msg_text
        
        if is_link or (potential_id and len(potential_id) > 20 and " " not in msg_text):
            # Try registration
            await register_sheet(update, context, potential_id)
            return
    
    # Otherwise, treat as note (including forwards)
    await save_note(update, context)

async def register_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE, spreadsheet_id: str):
    storage: GoogleSheetsStorage = context.bot_data['storage']
    user_id = update.effective_user.id
    
    if not spreadsheet_id:
        await update.message.reply_text("❌ Не удалось распознать ID таблицы.")
        return

    status_msg = await update.message.reply_text("⏳ Проверяю доступ к таблице...")
    
    has_access, error_msg = await storage.check_access(spreadsheet_id)
    
    if has_access:
        save_user(user_id, spreadsheet_id)
        # Initialize headers
        await status_msg.edit_text("⏳ Настраиваю заголовки таблицы...")
        await storage.ensure_headers(spreadsheet_id)
        
        await status_msg.edit_text(
            "✅ **Успешно!** Таблица подключена.\n\n"
            "Теперь просто пишите мне сообщения, и я буду сохранять их как заметки.\n"
            "Теги (слова с #) будут автоматически распознаны.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        email = storage.get_service_account_email()
        await status_msg.edit_text(
            "❌ **Нет доступа.**\n"
            f"⚠️ Ошибка: `{error_msg}`\n\n"
            "Убедитесь, что вы дали доступ Редактора этому email:\n"
            f"`{email}`\n\n"
            "Попробуйте снова после настройки доступа.",
            parse_mode=ParseMode.MARKDOWN
        )

async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: GoogleSheetsStorage = context.bot_data['storage']
    user_id = update.effective_user.id
    spreadsheet_id = get_user_spreadsheet(user_id)
    
    if not spreadsheet_id:
        await update.message.reply_text("⚠️ Вы еще не подключили таблицу. Нажмите /start для инструкции.")
        return

    # Detect if this is a forwarded message
    is_forward = update.message.forward_origin is not None
    
    # For MEDIA forwards (photo/video/doc), caption is user's comment
    caption = update.message.caption or ""
    # For TEXT forwards, text contains EITHER user's comment OR the forwarded text
    text = update.message.text or ""
    
    # Check if this is a media message
    has_media = bool(update.message.photo or update.message.video or update.message.document or update.message.audio)
    
    logging.info(f"is_forward={is_forward}, has_media={has_media}, has_caption={bool(caption)}, has_text={bool(text)}")
    
    messages_to_save = []
    
    # Case 1: Media forward with caption (save both)
    if is_forward and has_media and caption:
        # First, save the caption as a general message
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
        
        # Then, save the forwarded media reference
        telegram_username = _get_forward_username(update.message)
        forward_note = {
            'message_id': update.message.message_id,
            'content': '[Media]',
            'tags': [],
            'reply_to_message_id': None,
            'message_type': 'forwarded',
            'source_chat_id': _get_forward_chat_id(update.message),
            'source_chat_link': _get_forward_chat_link(update.message),
            'telegram_username': telegram_username
        }
        messages_to_save.append(forward_note)
    
    # Case 2: Pure forward (text or media without caption)
    elif is_forward:
        forward_content = _extract_forward_content(update.message)
        telegram_username = _get_forward_username(update.message)
        forward_note = {
            'message_id': update.message.message_id,
            'content': forward_content,
            'tags': [],
            'reply_to_message_id': update.message.reply_to_message.message_id if update.message.reply_to_message else None,
            'message_type': 'forwarded',
            'source_chat_id': _get_forward_chat_id(update.message),
            'source_chat_link': _get_forward_chat_link(update.message),
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

def _extract_forward_content(message) -> str:
    """Extract content from forwarded message (not the caption)."""
    # For forwarded messages, we want the ORIGINAL content, not the caption
    if message.text:
        return message.text
    elif message.photo or message.video or message.document or message.audio:
        # Media forward - check if original had caption
        # Note: Telegram doesn't preserve original caption in forward_origin
        return "[Media]"
    else:
        return "[Unsupported media type]"

def _get_forward_chat_id(message) -> int:
    """Get the chat ID from where the message was forwarded."""
    if hasattr(message.forward_origin, 'sender_user'):
        return message.forward_origin.sender_user.id
    elif hasattr(message.forward_origin, 'sender_chat'):
        return message.forward_origin.sender_chat.id
    elif hasattr(message.forward_origin, 'chat'):
        return message.forward_origin.chat.id
    return 0

def _get_forward_username(message) -> str:
    """Get the username from the forward source (user or channel)."""
    origin = message.forward_origin
    
    # User forward
    if hasattr(origin, 'sender_user'):
        user = origin.sender_user
        return getattr(user, 'username', '')
    
    # Channel/Group forward
    elif hasattr(origin, 'chat'):
        chat = origin.chat
        return getattr(chat, 'username', '')
    
    elif hasattr(origin, 'sender_chat'):
        chat = origin.sender_chat
        return getattr(chat, 'username', '')
    
    return ""

def _get_forward_chat_link(message) -> str:
    """Generate a link to the source chat/user."""
    origin = message.forward_origin
    
    # User forward
    if hasattr(origin, 'sender_user'):
        user = origin.sender_user
        username = getattr(user, 'username', None)
        if username:
            return f"https://t.me/{username}"
        else:
            return f"User ID: {user.id}"
    
    # Channel forward
    elif hasattr(origin, 'chat'):
        chat = origin.chat
        message_id = getattr(origin, 'message_id', None)
        
        if chat.username:
            # Public channel with message link
            if message_id:
                return f"https://t.me/{chat.username}/{message_id}"
            else:
                return f"https://t.me/{chat.username}"
        else:
            return f"Chat ID: {chat.id}"
    
    # Group/Supergroup forward (has sender_chat)
    elif hasattr(origin, 'sender_chat'):
        chat = origin.sender_chat
        # Try to get the original sender user if available
        sender_user_info = ""
        if hasattr(message, 'forward_from'):
            sender_user_info = f" (from user {message.forward_from.id})"
        
        if chat.username:
            return f"https://t.me/{chat.username}{sender_user_info}"
        else:
            return f"Chat ID: {chat.id}{sender_user_info}"
    
    # Hidden user or other
    return "Hidden/Unknown"
