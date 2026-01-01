import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_config():
    """
    Loads and validates configuration variables.
    Returns a dictionary with config values.
    Exits the program if critical variables are missing.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

    missing = []
    if not bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not credentials_path:
        missing.append("GOOGLE_SHEETS_CREDENTIALS")
    
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Please check your .env file.")
        sys.exit(1)
        
    # Check if credentials is a file path or JSON content
    if credentials_path.strip().startswith('{'):
        # It's likely a JSON string (Railway style)
        pass
    elif not os.path.exists(credentials_path):
        print(f"Error: Credentials file not found at: {credentials_path}")
        sys.exit(1)

    # OpenAI API key (optional - for voice transcription)
    openai_api_key = os.getenv("OPENAI_API_KEY")

    return {
        "bot_token": bot_token,
        "credentials_path": credentials_path,
        "openai_api_key": openai_api_key
    }

# Load config on import to fail fast
config = load_config()
