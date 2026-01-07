from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from config import config
from storage.google_sheets import GoogleSheetsStorage
from services import NoteService
from services.relation_service import RelationService
from schemas import StatusUpdate, NotesResponse, RelatedNotesResponse, ReplyChainResponse
from bot.utils import get_user_spreadsheet

app = FastAPI()

# Initialize storage and services
storage = GoogleSheetsStorage(credentials_path=config['credentials_path'])
note_service = NoteService(storage)
relation_service = RelationService(storage)

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

@app.get("/api.js")
async def get_api_js():
    """Serve API JS file"""
    return FileResponse("webapp/api.js")

@app.get("/state.js")
async def get_state_js():
    """Serve State JS file"""
    return FileResponse("webapp/state.js")

@app.get("/ui.js")
async def get_ui_js():
    """Serve UI JS file"""
    return FileResponse("webapp/ui.js")

@app.post("/api/notes/{note_id}/status")
async def update_note_status(note_id: str, update: StatusUpdate):
    """
    Update the status of a note.
    """
    try:
        success = await note_service.update_note_status(update.user_id, note_id, update.status)
        
        if not success:
            # We don't distinguish between "user not found" and "note not found" here for simplicity,
            # but in a real app we might want to be more specific.
            # If user not found, get_user_spreadsheet returns None, service returns False.
            raise HTTPException(status_code=404, detail="Note not found or update failed")
            
        return {"status": "success", "new_status": update.status}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes")
async def get_notes(user_id: int = Query(None)):
    """
    Get all notes for a user from their Google Sheet.
    Filters out 'archived' and 'done'.
    Sorts 'focus' to the top.
    """
    try:
        # If no user_id provided, return demo data
        if user_id is None:
            return note_service.get_demo_notes()

        response = await note_service.get_user_notes(user_id)

        if response is None:
             raise HTTPException(status_code=404, detail="User not registered")

        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes/{note_id}/related", response_model=RelatedNotesResponse)
async def get_related_notes(note_id: str, user_id: int = Query(...)):
    """
    Get notes related to the specified note based on common tags.

    Args:
        note_id: The ID of the note to find relations for (Column A in Google Sheets)
        user_id: The Telegram user ID

    Returns:
        RelatedNotesResponse with sorted list of related notes

    Algorithm:
        1. Finds all notes with at least one common tag
        2. Sorts by: common_tags_count DESC, created_at DESC
        3. Includes all statuses (new, focus, done, archived)
    """
    try:
        # Get user's spreadsheet ID
        spreadsheet_id = get_user_spreadsheet(user_id)
        if not spreadsheet_id:
            raise HTTPException(status_code=404, detail="User not registered")

        # Compute related notes
        related_notes = await relation_service.get_related_notes(
            note_id=note_id,
            spreadsheet_id=spreadsheet_id
        )

        return RelatedNotesResponse(
            related=related_notes,
            total=len(related_notes),
            note_id=note_id
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching related notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notes/{note_id}/replies", response_model=ReplyChainResponse)
async def get_reply_chain(note_id: str, user_id: int = Query(...)):
    """
    Get reply chain for the specified note.

    Args:
        note_id: The ID of the note to build chain for
        user_id: The Telegram user ID

    Returns:
        ReplyChainResponse with chain, stats, and navigation info

    Algorithm:
        1. Finds ancestors (path up to root)
        2. Finds descendants (following first reply at each level)
        3. Returns chain with navigation stats
    """
    try:
        # Get user's spreadsheet ID
        spreadsheet_id = get_user_spreadsheet(user_id)
        if not spreadsheet_id:
            raise HTTPException(status_code=404, detail="User not registered")

        # Build reply chain
        result = await relation_service.get_reply_chain(
            note_id=note_id,
            spreadsheet_id=spreadsheet_id
        )

        return ReplyChainResponse(
            chain=result['chain'],
            current_index=result['current_index'],
            stats=result['stats'],
            branches=result['branches'],
            note_id=note_id
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching reply chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
