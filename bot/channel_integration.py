import json
import os
import logging
from typing import Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from .utils import get_user_spreadsheet

CHANNEL_MAP_FILE = 'channel_map.json'

def load_channel_mapping() -> Dict[str, int]:
    if not os.path.exists(CHANNEL_MAP_FILE):
        return {}
    try:
        with open(CHANNEL_MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_channel_mapping(channel_id: int, user_id: int):
    mapping = load_channel_mapping()
    mapping[str(channel_id)] = user_id
    with open(CHANNEL_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4)

def get_user_for_channel(channel_id: int) -> Optional[int]:
    mapping = load_channel_mapping()
    return mapping.get(str(channel_id))

CHANNEL_MSG_MAP_FILE = 'channel_messages.json'

def load_message_mapping() -> Dict[str, int]:
    if not os.path.exists(CHANNEL_MSG_MAP_FILE):
        return {}
    try:
        with open(CHANNEL_MSG_MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_message_mapping(channel_id: int, post_id: int, cloned_id: int):
    mapping = load_message_mapping()
    key = f"{channel_id}:{post_id}"
    mapping[key] = cloned_id
    with open(CHANNEL_MSG_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4)

def get_cloned_message_id(channel_id: int, post_id: int) -> Optional[int]:
    mapping = load_message_mapping()
    key = f"{channel_id}:{post_id}"
    return mapping.get(key)

async def link_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /link_channel command.
    User must reply to a forwarded message from the channel they want to link.
    """
    user_id = update.effective_user.id
    message = update.message
    
    # Check if it's a reply
    if not message.reply_to_message:
        await message.reply_text("⚠️ Ответьте этой командой на пересланное сообщение из канала.")
        return

    reply = message.reply_to_message
    
    # Check if the replied message is a forward from a channel
    if not reply.forward_origin or reply.forward_origin.type != 'channel':
        await message.reply_text("⚠️ Это сообщение не похоже на пересылку из канала.")
        return

    channel_id = reply.forward_origin.chat.id
    channel_title = reply.forward_origin.chat.title
    
    # Save mapping
    save_channel_mapping(channel_id, user_id)
    
    await message.reply_text(
        f"✅ **Канал подключен!**\n\n"
        f"Канал: `{channel_title}` (ID: `{channel_id}`)\n"
        f"Теперь сообщения из этого канала будут сохраняться в вашу таблицу.",
        parse_mode=ParseMode.MARKDOWN
    )

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles posts in channels.
    """
    logging.info(f"Received channel post update: {update}")
    
    if not update.channel_post:
        logging.info("Update is not a channel_post")
        return

    channel_id = update.channel_post.chat.id
    logging.info(f"Processing post from channel {channel_id}")
    
    user_id = get_user_for_channel(channel_id)
    logging.info(f"Mapped user_id: {user_id}")
    
    if not user_id:
        # Channel not linked to any user
        return

    spreadsheet_id = get_user_spreadsheet(user_id)
    if not spreadsheet_id:
        logging.warning(f"User {user_id} linked to channel {channel_id} has no spreadsheet.")
        return

    post = update.channel_post
    content = post.text or post.caption or ""
    tags = [word for word in content.split() if word.startswith('#')]
    
    # Construct note data
    note_data = {
        'message_id': post.message_id,
        'content': content,
        'tags': tags,
        'reply_to_message_id': None,
        'message_type': 'channel_post',
        'source_chat_id': channel_id,
        'source_chat_link': '',
        'telegram_username': post.chat.username or post.chat.title
    }
    
    # Handle public channel links better if username exists
    if post.chat.username:
        note_data['source_chat_link'] = f"https://t.me/{post.chat.username}/{post.message_id}"
    else:
         # Rough approximation for private channels (might not work for all)
         # Channel IDs start with -100, remove that for link
        cid_str = str(channel_id)
        if cid_str.startswith('-100'):
             cid_str = cid_str[4:]
        note_data['source_chat_link'] = f"https://t.me/c/{cid_str}/{post.message_id}"


    storage = context.bot_data['storage']
    try:
        await storage.save_note(spreadsheet_id, note_data)
        logging.info(f"Saved channel post {post.message_id} from {channel_id} for user {user_id}")
        
        # Clone (copy) the message to the bot's chat with the user
        try:
            cloned_msg = await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=channel_id,
                message_id=post.message_id
            )
            # Save mapping for future edits
            save_message_mapping(channel_id, post.message_id, cloned_msg.message_id)
            
        except Exception as e:
            logging.error(f"Error copying message to user {user_id}: {e}")
            
    except Exception as e:
        logging.error(f"Error saving channel post: {e}")

async def edited_channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles edited posts in channels.
    """
    if not update.edited_channel_post:
        return

    post = update.edited_channel_post
    channel_id = post.chat.id
    user_id = get_user_for_channel(channel_id)
    
    if not user_id:
        return

    spreadsheet_id = get_user_spreadsheet(user_id)
    if not spreadsheet_id:
        return

    new_content = post.text or post.caption or ""
    new_tags = [word for word in new_content.split() if word.startswith('#')]
    
    # 1. Update Google Sheet
    storage = context.bot_data['storage']
    try:
        # We use the original channel post ID as the message_id in the sheet
        await storage.update_note(spreadsheet_id, post.message_id, new_content, new_tags)
        logging.info(f"Updated note for channel post {post.message_id}")
    except Exception as e:
        logging.error(f"Error updating note in sheet: {e}")

    # 2. Update Cloned Message in Bot Chat
    cloned_msg_id = get_cloned_message_id(channel_id, post.message_id)
    if cloned_msg_id:
        try:
            if post.text:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=cloned_msg_id,
                    text=new_content
                )
            elif post.caption:
                await context.bot.edit_message_caption(
                    chat_id=user_id,
                    message_id=cloned_msg_id,
                    caption=new_content
                )
        except Exception as e:
            logging.error(f"Error updating cloned message: {e}")
