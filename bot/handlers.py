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

# Simple in-memory rate limiter: {user_id: last_message_timestamp}
user_last_activity = {}
RATE_LIMIT_SECONDS = 3.0

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle text messages (Registration or Notes).
    """
    user_id = update.effective_user.id
    current_time = time.time()
    
    # Rate Limiting Check
    last_time = user_last_activity.get(user_id, 0)
    if current_time - last_time < RATE_LIMIT_SECONDS:
        # Silently ignore or warn (silently is better for anti-spam)
        return
    
    user_last_activity[user_id] = current_time

    msg_text = update.message.text
    storage: GoogleSheetsStorage = context.bot_data['storage']
    
    # Check if it looks like a spreadsheet URL or ID
    # Simple heuristic: contains "docs.google.com" OR is a long alphanumeric string
    potential_id = extract_spreadsheet_id(msg_text)
    
    # If it looks like an ID and user explicitly sent it (maybe trying to register)
    # We prioritize registration if they don't have a sheet yet OR if it looks very much like a link
    
    is_link = "docs.google.com/spreadsheets" in msg_text
    
    if is_link or (potential_id and len(potential_id) > 20 and " " not in msg_text):
        # Try registration
        await register_sheet(update, context, potential_id)
    else:
        # Treat as note
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

    content = update.message.text
    tags = [word for word in content.split() if word.startswith('#')]
    reply_to_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
    
    note_data = {
        'message_id': update.message.message_id,
        'content': content,
        'tags': tags,
        'reply_to_message_id': reply_to_id
    }
    
    try:
        await storage.save_note(spreadsheet_id, note_data)
        await update.message.set_reaction(reaction=ReactionTypeEmoji(emoji="✍️"))
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при сохранении: {str(e)}")
