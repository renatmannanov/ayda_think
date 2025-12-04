# Forward message utilities

def extract_forward_content(message) -> str:
    """Extract content from forwarded message (not the caption)."""
    if message.text:
        return message.text
    elif message.photo or message.video or message.document or message.audio:
        return "[Media]"
    else:
        return "[Unsupported media type]"

def get_forward_chat_id(message) -> int:
    """Get the chat ID from where the message was forwarded."""
    if hasattr(message.forward_origin, 'sender_user'):
        return message.forward_origin.sender_user.id
    elif hasattr(message.forward_origin, 'sender_chat'):
        return message.forward_origin.sender_chat.id
    elif hasattr(message.forward_origin, 'chat'):
        return message.forward_origin.chat.id
    return 0

def get_forward_username(message) -> str:
    """Get the username from the forward source (user or channel)."""
    origin = message.forward_origin
    
    if hasattr(origin, 'sender_user'):
        user = origin.sender_user
        return getattr(user, 'username', '')
    elif hasattr(origin, 'chat'):
        chat = origin.chat
        return getattr(chat, 'username', '')
    elif hasattr(origin, 'sender_chat'):
        chat = origin.sender_chat
        return getattr(chat, 'username', '')
    
    return ""

def get_forward_chat_link(message) -> str:
    """Generate a link to the source chat/user."""
    origin = message.forward_origin
    
    # User forward
    if hasattr(origin, 'sender_user'):
        user = origin.sender_user
        username = getattr(user, 'username', None)
        if username:
            return f"https://t.me/{username}"
        else:
            return f"User ID: {user.id}"
    
    # Channel forward
    elif hasattr(origin, 'chat'):
        chat = origin.chat
        message_id = getattr(origin, 'message_id', None)
        
        if chat.username:
            if message_id:
                return f"https://t.me/{chat.username}/{message_id}"
            else:
                return f"https://t.me/{chat.username}"
        else:
            return f"Chat ID: {chat.id}"
    
    # Group/Supergroup forward
    elif hasattr(origin, 'sender_chat'):
        chat = origin.sender_chat
        sender_user_info = ""
        if hasattr(message, 'forward_from'):
            sender_user_info = f" (from user {message.forward_from.id})"
        
        if chat.username:
            return f"https://t.me/{chat.username}{sender_user_info}"
        else:
            return f"Chat ID: {chat.id}{sender_user_info}"
    
    return "Hidden/Unknown"
