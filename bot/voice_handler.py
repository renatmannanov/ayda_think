"""
Voice Handler - Download and process voice messages
Handles both direct messages and channel posts
"""
import os
import tempfile
import logging
from telegram import Update, Message
from telegram.ext import ContextTypes
from services.transcription_service import (
    transcribe_audio,
    improve_transcription,
    is_transcription_available
)


async def download_voice_file(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Download voice/audio file from Telegram to a temporary file

    Args:
        message: Telegram message containing voice/audio
        context: Bot context

    Returns:
        Path to downloaded temporary file

    Raises:
        ValueError: If no voice/audio in message
    """
    # Get voice or audio attachment
    voice = message.voice
    audio = message.audio

    if voice:
        file_id = voice.file_id
        suffix = ".ogg"
    elif audio:
        file_id = audio.file_id
        # Try to get extension from mime type
        mime = audio.mime_type or ""
        if "mp3" in mime or "mpeg" in mime:
            suffix = ".mp3"
        elif "wav" in mime:
            suffix = ".wav"
        elif "m4a" in mime or "mp4" in mime:
            suffix = ".m4a"
        else:
            suffix = ".ogg"
    else:
        raise ValueError("No voice or audio in message")

    # Download file
    file = await context.bot.get_file(file_id)

    # Create temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    tmp.close()

    await file.download_to_drive(tmp_path)
    logging.info(f"Downloaded voice to: {tmp_path}")

    return tmp_path


async def process_voice_message(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    improve: bool = False
) -> dict:
    """
    Full voice message processing pipeline:
    1. Download audio file
    2. Transcribe with Whisper
    3. (Optional) Improve with GPT
    4. Return data for saving

    Args:
        message: Telegram message with voice/audio
        context: Bot context
        improve: Whether to post-process with GPT (costs extra)

    Returns:
        dict with:
            - content: transcribed text
            - duration: audio duration in seconds
            - original_type: 'voice' or 'audio'

    Returns None if transcription not available or failed
    """
    if not is_transcription_available():
        logging.warning("Transcription not available - OPENAI_API_KEY not set")
        return None

    voice = message.voice
    audio = message.audio

    if not voice and not audio:
        return None

    file_path = None
    try:
        # Download
        file_path = await download_voice_file(message, context)

        # Transcribe
        text = await transcribe_audio(file_path)

        if not text:
            logging.warning("Empty transcription result")
            return None

        # Optional: improve with GPT
        if improve and len(text) > 10:
            logging.info(f"Improving transcription with GPT...")
            text = await improve_transcription(text)
            logging.info(f"Improved transcription: {text[:100]}...")

        # Determine type and duration
        if voice:
            original_type = "voice"
            duration = voice.duration
        else:
            original_type = "audio"
            duration = audio.duration if audio.duration else None

        return {
            "content": text,
            "duration": duration,
            "original_type": original_type
        }

    except Exception as e:
        logging.error(f"Voice processing error: {e}")
        return None

    finally:
        # Cleanup temp file
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logging.warning(f"Failed to cleanup temp file: {e}")


def has_voice_or_audio(message: Message) -> bool:
    """Check if message contains voice or audio"""
    return bool(message.voice or message.audio)
