import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from storage.google_sheets import GoogleSheetsStorage
from storage.db import init_db
from config import config
from bot.handlers import start, handle_message, handle_edited_message

from bot.channel_integration import link_channel_handler, channel_post_handler, edited_channel_post_handler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    # Initialize database
    logging.info("Initializing database...")
    init_db()
    
    # Initialize storage
    storage = GoogleSheetsStorage(credentials_path=config['credentials_path'])
    
    # Initialize Application
    application = ApplicationBuilder().token(config['bot_token']).build()
    
    # Store storage in bot_data so handlers can access it
    application.bot_data['storage'] = storage
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("link_channel", link_channel_handler))
    
    # Handle channel posts
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
    
    # Handle edited channel posts
    application.add_handler(MessageHandler(filters.UpdateType.EDITED_CHANNEL_POST, edited_channel_post_handler))
    
    # Handle all messages (text, forwards, media with captions) - but NOT edited
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE, 
        handle_message
    ))
    
    # Handle edited messages separately
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & filters.UpdateType.EDITED_MESSAGE,
        handle_edited_message
    ))
    
    print("Bot is running (python-telegram-bot)...")
    # Explicitly allow channel_post updates
    # Drop pending updates to avoid conflicts with other instances
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
