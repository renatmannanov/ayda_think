from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from config import config
from storage.google_sheets import GoogleSheetsStorage
from services import NoteService
from schemas import StatusUpdate, NotesResponse

app = FastAPI()

# Initialize storage and service
storage = GoogleSheetsStorage(credentials_path=config['credentials_path'])
note_service = NoteService(storage)

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

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
