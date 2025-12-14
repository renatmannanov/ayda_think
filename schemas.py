from pydantic import BaseModel
from typing import List, Optional

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

class RelatedNote(BaseModel):
    """Note with additional metadata about relationship strength."""
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
    common_tags_count: int  # Number of tags in common with the target note

class RelatedNotesResponse(BaseModel):
    """Response containing related notes."""
    related: List[RelatedNote]
    total: int
    note_id: str  # ID of the note these are related to
