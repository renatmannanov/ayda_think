from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from storage.google_sheets import GoogleSheetsStorage
from .utils import save_user

async def register_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE, spreadsheet_id: str):
    """
    Handle spreadsheet registration.
    """
    storage: GoogleSheetsStorage = context.bot_data['storage']
    user_id = update.effective_user.id
    
    if not spreadsheet_id:
        await update.message.reply_text("❌ Не удалось распознать ID таблицы.")
        return

    status_msg = await update.message.reply_text("⏳ Проверяю доступ к таблице...")
    
    has_access, error_msg = await storage.check_access(spreadsheet_id)
    
    if has_access:
        save_user(user_id, spreadsheet_id)
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
