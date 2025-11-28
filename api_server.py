from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from storage.google_sheets import GoogleSheetsStorage
from bot.utils import get_user_spreadsheet
from config import config

app = FastAPI()

# Initialize storage
storage = GoogleSheetsStorage(credentials_path=config['credentials_path'])

class Note(BaseModel):
    id: str
    telegram_message_id: str
    created_at: str
    content: str
    tags: str
    reply_to_message_id: Optional[str] = None
    message_type: str
    source_chat_id: Optional[str] = None
    source_chat_link: Optional[str] = None
    telegram_username: Optional[str] = None
    status: Optional[str] = ""

class NotesResponse(BaseModel):
    notes: List[Note]
    total: int

class StatusUpdate(BaseModel):
    status: str
    user_id: int

@app.get("/")
async def root():
    """Serve the main webapp page"""
    return FileResponse("webapp/index.html")

@app.get("/styles.css")
async def get_styles():
    """Serve CSS file"""
    return FileResponse("webapp/styles.css")

@app.get("/app.js")
async def get_app_js():
    """Serve JS file"""
    return FileResponse("webapp/app.js")

@app.post("/api/notes/{note_id}/status")
async def update_note_status(note_id: str, update: StatusUpdate):
    """
    Update the status of a note.
    """
    try:
        spreadsheet_id = get_user_spreadsheet(update.user_id)
        if not spreadsheet_id:
            raise HTTPException(status_code=404, detail="User not registered")
            
        success = await storage.update_note_status(spreadsheet_id, note_id, update.status)
        
        if not success:
            raise HTTPException(status_code=404, detail="Note not found or update failed")
            
        return {"status": "success", "new_status": update.status}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes")
async def get_notes(user_id: Optional[int] = Query(None)):
    """
    Get all notes for a user from their Google Sheet.
    Filters out 'archived' and 'done'.
    Sorts 'focus' to the top.
    """
    try:
        # If no user_id provided, return demo data
        if user_id is None:
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
        
        # Get user's spreadsheet ID
        spreadsheet_id = get_user_spreadsheet(user_id)
        print(f"User {user_id} -> Spreadsheet ID: {spreadsheet_id}")
        
        if not spreadsheet_id:
            print(f"User {user_id} not registered")
            raise HTTPException(status_code=404, detail="User not registered")
        
        # Fetch notes from Google Sheets
        notes_data = await asyncio.to_thread(
            storage._get_all_notes_sync, 
            spreadsheet_id
        )
        
        print(f"Fetched {len(notes_data)} rows from spreadsheet")
        
        # Convert to Note objects
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
        # Assuming input is already roughly sorted by date (append order)
        # We want newest first, so reverse the list first
        notes.reverse()
        
        # Then stable sort to put focus at top
        notes.sort(key=lambda x: 0 if x.status == "focus" else 1)
        
        print(f"Converted {len(notes)} notes")
        return NotesResponse(notes=notes, total=len(notes))
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
