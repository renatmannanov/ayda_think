"""
Transcription Service - OpenAI Whisper API integration
Handles voice message transcription with optional GPT post-processing
"""
import logging
from openai import OpenAI
from config import config

# Initialize OpenAI client (lazy - only if key exists)
_client = None

def get_openai_client() -> OpenAI:
    """Get or create OpenAI client"""
    global _client
    if _client is None:
        api_key = config.get("openai_api_key")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured. Add it to .env file.")
        _client = OpenAI(api_key=api_key)
    return _client


def is_transcription_available() -> bool:
    """Check if transcription service is available (API key configured)"""
    return bool(config.get("openai_api_key"))


async def transcribe_audio(file_path: str, language: str = "ru") -> str:
    """
    Transcribe audio file using OpenAI Whisper API

    Args:
        file_path: Path to audio file (.ogg, .mp3, .wav, .m4a)
        language: Language code (ru, en, etc.) - helps accuracy

    Returns:
        Transcribed text

    Raises:
        ValueError: If API key not configured
        Exception: On API errors
    """
    client = get_openai_client()

    logging.info(f"Transcribing audio file: {file_path}")

    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language
        )

    text = transcript.text.strip()
    logging.info(f"Transcription complete: {len(text)} chars")

    return text


async def improve_transcription(raw_text: str) -> str:
    """
    Improve transcription using GPT-4o-mini
    - Removes filler words (um, uh, etc.)
    - Fixes punctuation
    - Preserves original meaning

    Args:
        raw_text: Raw transcription from Whisper

    Returns:
        Cleaned up text
    """
    if not raw_text or len(raw_text) < 10:
        return raw_text

    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": """You are a text editor. Clean up voice transcription:
- Remove filler words (um, uh, like, you know, э-э, ну, типа)
- Fix punctuation and capitalization
- Remove false starts and repetitions
- Split text into logical paragraphs (separate by blank line) when topic or thought changes
- Keep the EXACT meaning - do not add or remove information
- Keep the same language as input
- Output ONLY the cleaned text, nothing else"""
        }, {
            "role": "user",
            "content": raw_text
        }],
        temperature=0.3,
        max_tokens=len(raw_text) * 2  # Allow some expansion
    )

    improved = response.choices[0].message.content.strip()
    logging.info(f"Text improved: {len(raw_text)} -> {len(improved)} chars")

    return improved
