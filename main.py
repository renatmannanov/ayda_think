import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import config
from storage.google_sheets import GoogleSheetsStorage
from bot.handlers import start, handle_message

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    # Initialize storage
    storage = GoogleSheetsStorage(credentials_path=config['credentials_path'])
    
    # Initialize Application
    application = ApplicationBuilder().token(config['bot_token']).build()
    
    # Store storage in bot_data so handlers can access it
    application.bot_data['storage'] = storage
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    
    # Handle all messages (text, forwards, media with captions)
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND, 
        handle_message
    ))
    
    print("Bot is running (python-telegram-bot)...")
    application.run_polling()

if __name__ == "__main__":
    main()
