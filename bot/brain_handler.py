"""
Brain Handler — /search and /normalize bot commands.
/search [query] — semantic search across fragments.
/normalize — run normalization on unembedded fragments (admin only).
"""
import logging
import os
from telegram import Update
from telegram.ext import ContextTypes

from sqlalchemy import text as sa_text

from services.transcription_service import get_openai_client
from services.normalizer_service import normalize_all
from storage.fragments_db import search_by_embedding, get_fragments_count, Fragment, _pgvector_available
from storage.db import SessionLocal, engine

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

    status_msg = await message.reply_text("⏳ Запускаю нормализацию...")

    try:
        # Diagnostic: check mapper, raw SQL, ORM
        import storage.db as _db
        mapper_cols = [c.key for c in Fragment.__table__.columns]
        has_emb_attr = hasattr(Fragment, 'embedding')
        has_emb_col = 'embedding' in mapper_cols
        pgv = _pgvector_available()
        pgv_db = _db.pgvector_available

        with engine.connect() as conn:
            raw_total = conn.execute(sa_text("SELECT count(*) FROM fragments")).scalar()
            raw_null_emb = conn.execute(sa_text(
                "SELECT count(*) FROM fragments WHERE embedding IS NULL"
            )).scalar()

        session = SessionLocal()
        try:
            orm_null = session.query(Fragment).filter(
                Fragment.embedding.is_(None)
            ).count() if has_emb_attr else -1
        except Exception as ex:
            orm_null = f"ERROR: {ex}"
        finally:
            session.close()

        diag = (
            f"DIAG: pgv_import={True}, pgv_db={pgv_db}, pgv_avail={pgv}\n"
            f"  has_emb_attr={has_emb_attr}, has_emb_col={has_emb_col}\n"
            f"  mapper_cols={mapper_cols}\n"
            f"  raw_total={raw_total}, raw_null_emb={raw_null_emb}\n"
            f"  orm_null_emb={orm_null}"
        )
        logger.info(diag)

        result = normalize_all()
        total = get_fragments_count()
        await status_msg.edit_text(
            f"✅ Нормализация завершена:\n"
            f"  Эмбеддинги: {result['embedded']}\n"
            f"  Дубликаты: {result['duplicates']}\n"
            f"  Ошибки: {result['errors']}\n"
            f"  Всего в БД: {total}\n\n"
            f"DEBUG:\n{diag}"
        )
    except Exception as e:
        logger.error(f"Normalize error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка нормализации: {e}")
