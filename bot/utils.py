import re
from typing import Optional
from storage.db import get_user_spreadsheet as db_get_user, save_user as db_save_user

def save_user(user_id: int, spreadsheet_id: str):
    """Saves or updates a user's spreadsheet ID in the database."""
    db_save_user(user_id, spreadsheet_id)

def get_user_spreadsheet(user_id: int) -> Optional[str]:
    """Retrieves the spreadsheet ID for a given user from the database."""
    return db_get_user(user_id)

def extract_spreadsheet_id(url_or_id: str) -> Optional[str]:
    """
    Extracts the spreadsheet ID from a full URL or returns the ID if it looks like one.
    """
    # Regex for extracting ID from URL
    # Matches strings like /d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url_or_id)
    if match:
        return match.group(1)
    
    # If it's just the ID (alphanumeric + -_), return it
    if re.match(r'^[a-zA-Z0-9-_]+$', url_or_id):
        return url_or_id
        
    return None
