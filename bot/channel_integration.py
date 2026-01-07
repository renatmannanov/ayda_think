import json
import os
import logging
from typing import Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from .utils import get_user_spreadsheet
from .voice_handler import process_voice_message, has_voice_or_audio

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
    post = update.channel_post
    post_text = post.text or ""

    # Check if this is a /tag command in channel
    if post_text.startswith('/tag') and post.reply_to_message:
        await handle_channel_tag_command(update, context)
        return

    logging.info(f"Processing post from channel {channel_id}")

    # Debug: log reply_to_message details
    if post.reply_to_message:
        rtm = post.reply_to_message
        logging.info(f"DEBUG reply_to_message: chat_id={rtm.chat.id}, msg_id={rtm.message_id}, chat_type={rtm.chat.type}")
    else:
        logging.info("DEBUG: No reply_to_message")

    user_id = get_user_for_channel(channel_id)
    logging.info(f"Mapped user_id: {user_id}")

    if not user_id:
        # Channel not linked to any user
        return

    spreadsheet_id = get_user_spreadsheet(user_id)
    if not spreadsheet_id:
        logging.warning(f"User {user_id} linked to channel {channel_id} has no spreadsheet.")
        return

    storage = context.bot_data['storage']

    # Handle voice messages from channel
    if has_voice_or_audio(post):
        # Step 1: Send "processing" reply to channel
        try:
            status_msg = await context.bot.send_message(
                chat_id=channel_id,
                text="🎤 Транскрибирую и форматирую...",
                reply_to_message_id=post.message_id
            )
        except Exception as e:
            logging.error(f"Cannot reply to channel (not admin?): {e}")
            # Notify user via DM
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Не могу отправить сообщение в канал.\n"
                         f"Сделайте бота администратором канала с правом отправки сообщений."
                )
            except:
                pass
            status_msg = None

        # Step 2: Transcribe
        voice_data = await process_voice_message(post, context, improve=True)

        if voice_data:
            content = voice_data["content"]
            message_type = "channel_voice"
            logging.info(f"Transcribed voice from channel: {len(content)} chars")

            # Step 3: Edit reply with transcription
            if status_msg:
                try:
                    await status_msg.edit_text(content)
                except Exception as e:
                    logging.error(f"Error editing channel message: {e}")

            # Use transcription message ID for saving
            save_message_id = status_msg.message_id if status_msg else post.message_id
        else:
            content = "[Voice message - transcription unavailable]"
            message_type = "channel_post"
            logging.warning("Voice transcription failed for channel post")
            if status_msg:
                try:
                    await status_msg.edit_text("❌ Не удалось расшифровать голосовое сообщение.")
                except:
                    pass
            save_message_id = post.message_id
    else:
        content = post.text or post.caption or ""
        message_type = "channel_post"
        save_message_id = post.message_id

    tags = [word for word in content.split() if word.startswith('#')]

    # Determine reply_to_message_id:
    # - For voice: link transcription to original voice post
    # - For regular posts: preserve reply chain if post is a reply to another message
    if has_voice_or_audio(post):
        reply_to_id = post.message_id  # Transcription replies to voice
    elif post.reply_to_message:
        reply_to_id = post.reply_to_message.message_id  # Preserve reply chain
    else:
        reply_to_id = None

    # Construct note data
    note_data = {
        'message_id': save_message_id,  # Use transcription msg ID for voice
        'content': content,
        'tags': tags,
        'reply_to_message_id': reply_to_id,
        'message_type': message_type,
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

    try:
        await storage.save_note(spreadsheet_id, note_data)
        logging.info(f"Saved channel post {post.message_id} from {channel_id} for user {user_id}")

        # Clone/send to user's bot chat
        if has_voice_or_audio(post):
            # For voice: send transcription text to user
            try:
                user_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text=content
                )
                # Save mapping: use status_msg.message_id (transcription in channel) for edits
                if status_msg:
                    save_message_mapping(channel_id, status_msg.message_id, user_msg.message_id)
            except Exception as e:
                logging.error(f"Error sending transcription to user {user_id}: {e}")
        else:
            # For non-voice: copy the original message
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
    Works for both regular posts and transcription replies (voice messages).
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
    # For voice transcriptions, the message_id in sheet is the transcription message ID (not voice)
    # For regular posts, it's the post.message_id
    # Either way, we use post.message_id since that's what we're editing
    storage = context.bot_data['storage']
    try:
        await storage.update_note(spreadsheet_id, post.message_id, new_content, new_tags)
        logging.info(f"Updated note for channel post {post.message_id}")
    except Exception as e:
        logging.error(f"Error updating note in sheet: {e}")

    # 2. Update Cloned/Sent Message in Bot Chat
    cloned_msg_id = get_cloned_message_id(channel_id, post.message_id)
    if cloned_msg_id:
        try:
            # Both regular posts and transcriptions are text messages in user's chat
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=cloned_msg_id,
                text=new_content
            )
            logging.info(f"Updated cloned message {cloned_msg_id} for user {user_id}")
        except Exception as e:
            logging.error(f"Error updating cloned message: {e}")


async def handle_channel_tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /tag command in channel.
    Usage: Reply to a message with /tag #one #two
    """
    post = update.channel_post
    channel_id = post.chat.id
    command_text = post.text or ""

    logging.info(f"Processing /tag command in channel {channel_id}")

    user_id = get_user_for_channel(channel_id)
    if not user_id:
        return

    spreadsheet_id = get_user_spreadsheet(user_id)
    if not spreadsheet_id:
        return

    # Extract tags from command
    tags = [word for word in command_text.split() if word.startswith('#')]
    if not tags:
        logging.info("No tags provided in /tag command")
        # Delete the command message anyway
        try:
            await context.bot.delete_message(chat_id=channel_id, message_id=post.message_id)
        except:
            pass
        return

    replied_msg = post.reply_to_message
    replied_msg_id = replied_msg.message_id

    # Get current content of replied message
    current_content = replied_msg.text or replied_msg.caption or ""

    # Append tags to content
    tags_string = " ".join(tags)
    new_content = f"{current_content}\n\n{tags_string}" if current_content else tags_string

    # Extract all tags from new content
    all_tags = [word for word in new_content.split() if word.startswith('#')]

    # Update in Google Sheets
    storage = context.bot_data['storage']
    try:
        await storage.update_note(spreadsheet_id, replied_msg_id, new_content, all_tags)
        logging.info(f"Added tags {tags} to channel message {replied_msg_id}")
    except Exception as e:
        logging.error(f"Error updating tags in sheet: {e}")

    # Try to edit the replied message in channel
    try:
        if replied_msg.text:
            await context.bot.edit_message_text(
                chat_id=channel_id,
                message_id=replied_msg_id,
                text=new_content
            )
        elif replied_msg.caption:
            await context.bot.edit_message_caption(
                chat_id=channel_id,
                message_id=replied_msg_id,
                caption=new_content
            )
        logging.info(f"Edited channel message {replied_msg_id} with new tags")
    except Exception as e:
        logging.info(f"Could not edit channel message: {e}")

    # Also update the cloned message in user's bot chat
    cloned_msg_id = get_cloned_message_id(channel_id, replied_msg_id)
    if cloned_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=cloned_msg_id,
                text=new_content
            )
            logging.info(f"Updated cloned message {cloned_msg_id} with tags")
        except Exception as e:
            logging.error(f"Error updating cloned message with tags: {e}")

    # Delete the /tag command message
    try:
        await context.bot.delete_message(chat_id=channel_id, message_id=post.message_id)
        logging.info(f"Deleted /tag command from channel")
    except Exception as e:
        logging.warning(f"Could not delete /tag command: {e}")
