import asyncio
import gspread
import logging
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

    async def save_note(self, spreadsheet_id: str, note_data: Dict[str, Any]) -> str:
        """Asynchronously save a note to Google Sheets."""
        return await asyncio.to_thread(self._save_note_sync, spreadsheet_id, note_data)

    async def update_note(self, spreadsheet_id: str, message_id: int, updated_content: str, updated_tags: list) -> bool:
        """Asynchronously update a note in Google Sheets by message_id."""
        return await asyncio.to_thread(self._update_note_sync, spreadsheet_id, message_id, updated_content, updated_tags)

    async def update_note_status(self, spreadsheet_id: str, note_id: str, new_status: str) -> bool:
        """Asynchronously update a note's status in Google Sheets by note_id (Column A)."""
        return await asyncio.to_thread(self._update_note_status_sync, spreadsheet_id, note_id, new_status)

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

    def _update_note_sync(self, spreadsheet_id: str, message_id: int, updated_content: str, updated_tags: list) -> bool:
        """Find and update a note by Telegram message_id."""
        try:
            sh = self.gc.open_by_key(spreadsheet_id)
            worksheet = sh.sheet1
            
            # Find the row with matching Telegram Message ID (column B)
            all_values = worksheet.get_all_values()
            
            for row_idx, row in enumerate(all_values[1:], start=2):  # Skip header, start from row 2
                if len(row) > 1 and row[1] == str(message_id):  # Column B (index 1)
                    # Formula Injection Protection
                    if updated_content and updated_content.startswith(('=', '+', '-', '@')):
                        updated_content = "'" + updated_content
                    
                    tags_str = ", ".join(updated_tags)
                    
                    # Update Content (column D) and Tags (column E)
                    worksheet.update_cell(row_idx, 4, updated_content)  # Column D
                    worksheet.update_cell(row_idx, 5, tags_str)  # Column E
                    
                    logging.info(f"Updated message {message_id} in row {row_idx}")
                    return True
            
            logging.warning(f"Message {message_id} not found in spreadsheet")
            return False
            
        except Exception as e:
            logging.error(f"Error updating note: {e}")
            return False

    def _update_note_status_sync(self, spreadsheet_id: str, note_id: str, new_status: str) -> bool:
        """Find and update a note's status by note_id."""
        try:
            sh = self.gc.open_by_key(spreadsheet_id)
            worksheet = sh.sheet1
            
            # Find the cell with the note_id (Column A)
            cell = worksheet.find(note_id)
            
            if cell:
                # Status is in column 11 (K)
                # cell.row gives the row number
                worksheet.update_cell(cell.row, 11, new_status)
                return True
            return False
            
        except Exception as e:
            logging.error(f"Error updating note status in sheet {spreadsheet_id}: {e}")
            return False

    def _save_note_sync(self, spreadsheet_id: str, note_data: Dict[str, Any]) -> str:
        """Synchronous implementation of save_note."""
        try:
            sh = self.gc.open_by_key(spreadsheet_id)
            worksheet = sh.sheet1  # Write to the first sheet
            
            self._ensure_headers_sync(spreadsheet_id)
            
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
            message_type = note_data.get('message_type', 'general')
            source_chat_id = note_data.get('source_chat_id', '')
            source_chat_link = note_data.get('source_chat_link', '')
            telegram_username = note_data.get('telegram_username', '')
            status = 'new'
            
            # Row: id | telegram_message_id | date_created | content | tags | reply_to_message_id | message_type | source_chat_id | source_chat_link | telegram_username | status
            row = [
                record_id,
                str(msg_id),
                created_at,
                content,
                tags_str,
                str(reply_to) if reply_to else '',
                message_type,
                str(source_chat_id) if source_chat_id else '',
                source_chat_link,
                telegram_username,
                status
            ]
            
            worksheet.append_row(row, table_range='A1')
            return record_id
            
        except Exception as e:
            # In a real app, we should log this properly
            print(f"Error saving to Google Sheets: {e}")
            raise e

    def _ensure_headers_sync(self, spreadsheet_id: str):
        try:
            sh = self.gc.open_by_key(spreadsheet_id)
            worksheet = sh.sheet1
            
            # Check if A1 is empty
            if not worksheet.acell('A1').value:
                headers = [
                    'ID', 
                    'Telegram Message ID', 
                    'Created At', 
                    'Content', 
                    'Tags', 
                    'Reply To Message ID',
                    'Message Type',
                    'Source Chat ID',
                    'Source Chat Link',
                    'Telegram Username',
                    'Status'
                ]
                worksheet.update('A1:K1', [headers])
            else:
                # Check if we need to add Status column (Column K, index 11)
                # Simple check: get header row
                headers = worksheet.row_values(1)
                if len(headers) < 11:
                    worksheet.update_cell(1, 11, 'Status')
                    
        except Exception as e:
            print(f"Error ensuring headers: {e}")
            # We don't raise here to not block registration if something minor fails

    def _get_all_notes_sync(self, spreadsheet_id: str) -> list:
        """Get all notes from a spreadsheet (excluding header row)."""
        try:
            sh = self.gc.open_by_key(spreadsheet_id)
            worksheet = sh.sheet1
            
            self._ensure_headers_sync(spreadsheet_id)
            
            # Get all values
            all_values = worksheet.get_all_values()
            
            # Return all rows except header (row 0)
            return all_values[1:] if len(all_values) > 1 else []
            
        except Exception as e:
            logging.error(f"Error fetching notes: {e}")
            return []
