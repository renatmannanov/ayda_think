import asyncio
import gspread
from datetime import datetime
from typing import Dict, Any
from .base import BaseStorage

class GoogleSheetsStorage(BaseStorage):
    def __init__(self, credentials_path: str):
        """
        Initialize the Google Sheets storage.
        
        Args:
            credentials_path: Path to the service account JSON credentials.
        """
        self.gc = gspread.service_account(filename=credentials_path)
        self.credentials_path = credentials_path

    def get_service_account_email(self) -> str:
        """Returns the client_email from the credentials file."""
        import json
        try:
            with open(self.credentials_path, 'r') as f:
                creds = json.load(f)
                return creds.get('client_email', 'Unknown')
        except Exception:
            return 'Unknown'

    async def save_note(self, destination_id: str, note_data: Dict[str, Any]) -> str:
        """
        Saves a note to a specific Google Sheet.
        
        Args:
            destination_id: The Google Spreadsheet ID.
            note_data: Dict containing:
                - message_id
                - content
                - tags (list)
                - reply_to_message_id (optional)
        
        Returns:
            The generated ID of the record.
        """
        # Run blocking network operations in a separate thread
        return await asyncio.to_thread(self._save_note_sync, destination_id, note_data)

    def _save_note_sync(self, spreadsheet_id: str, note_data: Dict[str, Any]) -> str:
        """Synchronous implementation of save_note."""
        try:
            sh = self.gc.open_by_key(spreadsheet_id)
            worksheet = sh.sheet1  # Write to the first sheet
            
            # Generate ID
            msg_id = note_data.get('message_id')
            record_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{msg_id}"
            created_at = datetime.now().isoformat()
            
            content = note_data.get('content', '')
            # Formula Injection Protection
            if content and content.startswith(('=', '+', '-', '@')):
                content = "'" + content
            
            tags_str = ", ".join(note_data.get('tags', []))
            reply_to = note_data.get('reply_to_message_id', '')
            
            # Row: id | telegram_message_id | date_created | content | tags | reply_to_message_id
            row = [
                record_id,
                str(msg_id),
                created_at,
                content,
                tags_str,
                str(reply_to) if reply_to else ''
            ]
            
            worksheet.append_row(row, table_range='A1')
            return record_id
            
        except Exception as e:
            # In a real app, we should log this properly
            print(f"Error saving to Google Sheets: {e}")
            raise e

    async def check_access(self, spreadsheet_id: str) -> tuple[bool, str]:
        """
        Checks if the service account has access to the spreadsheet.
        Returns: (is_accessible, error_message)
        """
        import traceback
        try:
            await asyncio.to_thread(self.gc.open_by_key, spreadsheet_id)
            return True, ""
        except Exception:
            error_details = traceback.format_exc()
            print(f"Error checking access: {error_details}")
            return False, error_details

    async def ensure_headers(self, spreadsheet_id: str):
        """
        Checks if the first row is empty and adds headers if needed.
        """
        await asyncio.to_thread(self._ensure_headers_sync, spreadsheet_id)

    def _ensure_headers_sync(self, spreadsheet_id: str):
        try:
            sh = self.gc.open_by_key(spreadsheet_id)
            worksheet = sh.sheet1
            
            # Check if A1 is empty
            if not worksheet.acell('A1').value:
                headers = ['ID', 'Telegram Message ID', 'Created At', 'Content', 'Tags', 'Reply To Message ID']
                worksheet.update('A1:F1', [headers])
        except Exception as e:
            print(f"Error ensuring headers: {e}")
            # We don't raise here to not block registration if something minor fails

