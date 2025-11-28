"""
Migration script to transfer users from users.json to database.
Run this once to migrate existing users.
"""
import json
import os
from storage.db import init_db, save_user

def migrate_users():
    """Migrate users from users.json to database."""
    users_file = 'users.json'
    
    if not os.path.exists(users_file):
        print(f"No {users_file} found. Skipping migration.")
        return
    
    # Initialize database
    print("Initializing database...")
    init_db()
    
    # Load users from JSON
    try:
        with open(users_file, 'r', encoding='utf-8') as f:
            users = json.load(f)
    except json.JSONDecodeError:
        print(f"Error reading {users_file}. File might be empty or corrupted.")
        return
    
    # Migrate each user
    migrated = 0
    for user_id_str, spreadsheet_id in users.items():
        try:
            user_id = int(user_id_str)
            save_user(user_id, spreadsheet_id)
            migrated += 1
            print(f"Migrated user {user_id} -> {spreadsheet_id}")
        except Exception as e:
            print(f"Error migrating user {user_id_str}: {e}")
    
    print(f"\nMigration complete! Migrated {migrated} users.")
    print(f"You can now safely delete {users_file} (it's backed up in git history).")

if __name__ == "__main__":
    migrate_users()
