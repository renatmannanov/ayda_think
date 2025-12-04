from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from storage.google_sheets import GoogleSheetsStorage
import logging

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command.
    """
    try:
        storage: GoogleSheetsStorage = context.bot_data['storage']
        email = storage.get_service_account_email()
        
        text = (
            "👋 Привет! Я бот для сохранения заметок в Google Таблицы.\n\n"
            "<b>Как начать:</b>\n"
            "1. Создайте новую Google Таблицу.\n"
            f"2. Нажмите 'Настройки доступа' (Share) и добавьте этот email:\n<code>{email}</code>\n(дайте права Редактора)\n"
            "3. Пришлите мне ссылку на таблицу (или её ID).\n\n"
            "После этого все ваши сообщения будут сохраняться туда!"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Error in start command: {e}")
        await update.message.reply_text(
            f"Привет! Произошла ошибка при форматировании сообщения, но я работаю.\nEmail бота: {email}\nОшибка: {e}"
        )
