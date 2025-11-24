import json
import re
import os
from typing import Dict, Optional

USERS_FILE = 'users.json'

def load_users() -> Dict[str, str]:
    """Loads users from the JSON file."""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_user(user_id: int, spreadsheet_id: str):
    """Saves or updates a user's spreadsheet ID."""
    users = load_users()
    users[str(user_id)] = spreadsheet_id
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)

def get_user_spreadsheet(user_id: int) -> Optional[str]:
    """Retrieves the spreadsheet ID for a given user."""
    users = load_users()
    return users.get(str(user_id))

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
