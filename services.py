import asyncio
from typing import List, Optional
from storage.google_sheets import GoogleSheetsStorage
from bot.utils import get_user_spreadsheet
from schemas import Note, NotesResponse

class NoteService:
    def __init__(self, storage: GoogleSheetsStorage):
        self.storage = storage

    async def get_user_notes(self, user_id: int) -> NotesResponse:
        """
        Fetches notes for a user, parses them, and sorts them.
        """
        # Get user's spreadsheet ID
        spreadsheet_id = get_user_spreadsheet(user_id)
        if not spreadsheet_id:
            return None # Or raise exception, handled in controller

        # Fetch notes from Google Sheets
        # Using the sync method wrapped in thread as per original implementation
        notes_data = await asyncio.to_thread(
            self.storage._get_all_notes_sync, 
            spreadsheet_id
        )
        
        notes = []
        for row in notes_data:
            if len(row) >= 9:
                status = row[10] if len(row) > 10 else ""
                
                note = Note(
                    id=row[0],
                    telegram_message_id=row[1],
                    created_at=row[2],
                    content=row[3],
                    tags=row[4],
                    reply_to_message_id=row[5] if row[5] else None,
                    message_type=row[6],
                    source_chat_id=row[7] if row[7] else None,
                    source_chat_link=row[8] if row[8] else None,
                    telegram_username=row[9] if len(row) > 9 and row[9] else None,
                    status=status
                )
                notes.append(note)
        
        # Sort: 'focus' first, then others by date (newest first)
        notes.reverse() # Newest first (assuming append order)
        notes.sort(key=lambda x: 0 if x.status == "focus" else 1)
        
        return NotesResponse(notes=notes, total=len(notes))

    async def update_note_status(self, user_id: int, note_id: str, status: str) -> bool:
        """
        Updates the status of a note.
        """
        spreadsheet_id = get_user_spreadsheet(user_id)
        if not spreadsheet_id:
            return False
            
        return await self.storage.update_note_status(spreadsheet_id, note_id, status)

    def get_demo_notes(self) -> NotesResponse:
        """
        Returns demo notes for testing.
        """
        demo_notes = [
            Note(
                id="demo_1",
                telegram_message_id="123",
                created_at="2024-11-24T14:30:00",
                content="Это демо-заметка с тегами для тестирования интерфейса",
                tags="#важно, #работа",
                message_type="general",
                status="focus"
            ),
            Note(
                id="demo_2",
                telegram_message_id="124",
                created_at="2024-11-24T14:31:00",
                content="Форвардированное сообщение из канала",
                tags="#новости",
                message_type="forwarded",
                status="new"
            )
        ]
        return NotesResponse(notes=demo_notes, total=len(demo_notes))
