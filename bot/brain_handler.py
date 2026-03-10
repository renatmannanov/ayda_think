"""
Brain Handler — /search and /normalize bot commands.
/search [query] — semantic search across fragments.
/normalize — run normalization on unembedded fragments (admin only).
"""
import logging
import os
from telegram import Update
from telegram.ext import ContextTypes

from services.transcription_service import get_openai_client
from services.normalizer_service import normalize_all
from storage.fragments_db import search_by_embedding, get_fragments_count

logger = logging.getLogger(__name__)

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))


def _make_telegram_link(external_id: str | None) -> str | None:
    """Build https://t.me/c/{channel_id}/{msg_id} from external_id like 'telegram_-100XXXXX_123'."""
    if not external_id or not external_id.startswith("telegram_"):
        return None
    parts = external_id.split("_", 2)  # ['telegram', '-100XXXXX', '123']
    if len(parts) < 3:
        return None
    channel_id_str = parts[1]
    msg_id = parts[2]
    # Remove -100 prefix for t.me/c/ links
    if channel_id_str.startswith("-100"):
        channel_id_str = channel_id_str[4:]
    return f"https://t.me/c/{channel_id_str}/{msg_id}"


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search [query] — semantic search across fragments.
    Usage: /search [N] query — N is optional result count (default 5, max 20).
    """
    message = update.message
    args = list(context.args) if context.args else []

    # Parse optional limit as first arg
    limit = 5
    if args and args[0].isdigit():
        limit = min(int(args.pop(0)), 20)

    query = " ".join(args)
    if not query:
        await message.reply_text("Использование: /search [N] <запрос>\nПример: /search чайный бизнес\nПример: /search 10 идеи для бизнеса")
        return

    try:
        # Get query embedding
        client = get_openai_client()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        query_embedding = response.data[0].embedding

        # Search
        results = search_by_embedding(query_embedding, limit=limit)

        if not results:
            await message.reply_text(f"🔍 По запросу \"{query}\" ничего не найдено.")
            return

        # Format response
        lines = [f"🔍 Поиск: \"{query}\"\n"]
        for i, r in enumerate(results, 1):
            date = r['created_at'][:10]
            text_preview = r['text'][:120].replace('\n', ' ')
            if len(r['text']) > 120:
                text_preview += "..."
            distance = f"[{r['distance']:.2f}]"
            link = _make_telegram_link(r.get('external_id'))

            line = f"{i}. {distance} {date}"
            line += f"\n   {text_preview}"
            if link:
                line += f"\n   {link}"
            lines.append(line)

        await message.reply_text("\n\n".join(lines), disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.reply_text(f"Ошибка поиска: {e}")


async def normalize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /normalize — run normalization (admin only)."""
    message = update.message
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await message.reply_text("⛔ Нет доступа.")
        return

    status_msg = await message.reply_text("⏳ Запускаю нормализацию...")

    try:
        result = normalize_all()
        total = get_fragments_count()
        await status_msg.edit_text(
            f"✅ Нормализация завершена:\n"
            f"  Эмбеддинги: {result['embedded']}\n"
            f"  Дубликаты: {result['duplicates']}\n"
            f"  Ошибки: {result['errors']}\n"
            f"  Всего в БД: {total}"
        )
    except Exception as e:
        logger.error(f"Normalize error: {e}")
        await status_msg.edit_text(f"❌ Ошибка нормализации: {e}")
