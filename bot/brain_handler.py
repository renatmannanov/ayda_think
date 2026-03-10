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
from storage.fragments_db import search_by_embedding, get_fragments_count, _pgvector_available
import storage.db as _db

logger = logging.getLogger(__name__)

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search [query] — semantic search across fragments."""
    message = update.message
    query = " ".join(context.args) if context.args else ""

    if not query:
        await message.reply_text("Использование: /search <запрос>\nПример: /search чайный бизнес")
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
        results = search_by_embedding(query_embedding, limit=5)

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
            tags = " ".join(r['tags']) if r['tags'] else ""
            distance = f"[{r['distance']:.2f}]"

            line = f"{i}. {distance} {date}"
            if tags:
                line += f"\n   {tags}"
            line += f"\n   {text_preview}"
            lines.append(line)

        await message.reply_text("\n\n".join(lines))

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

    # Diagnostic info
    total = get_fragments_count()
    pgv = _pgvector_available()
    pgv_db = _db.pgvector_available

    status_msg = await message.reply_text(
        f"⏳ Запускаю нормализацию...\n"
        f"  Фрагментов в БД: {total}\n"
        f"  pgvector (db): {pgv_db}\n"
        f"  pgvector (available): {pgv}"
    )

    try:
        result = normalize_all()
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
