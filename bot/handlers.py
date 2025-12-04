# Bot handlers - re-export hub for backward compatibility
# All handlers have been split into separate modules

from .start_handler import start
from .note_handler import handle_message, handle_edited_message
from .registration_handler import register_sheet
from .forward_utils import (
    extract_forward_content,
    get_forward_chat_id,
    get_forward_username,
    get_forward_chat_link
)

# Re-export all handlers for backward compatibility
__all__ = [
    'start',
    'handle_message',
    'handle_edited_message',
    'register_sheet',
    'extract_forward_content',
    'get_forward_chat_id',
    'get_forward_username',
    'get_forward_chat_link'
]
