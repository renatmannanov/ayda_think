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
from services.clustering_service import run_clustering
from storage.fragments_db import (
    search_by_embedding, search_hybrid, get_fragments_count,
    get_latest_cluster_version, get_clusters_by_version, get_cluster_fragments,
)

logger = logging.getLogger(__name__)

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))


_STOP_WORDS = frozenset(
    'с в на по для что как это или все мне мой где при так его ее них '
    'был быть есть нет без они она они мы вы уже еще бы же ли не но да '
    'от до из за об под над'.split()
)


def _stem_keyword(word: str) -> list[str]:
    """Generate ILIKE patterns: full word + trimmed stem for Cyrillic words.
    'Айкой' → ['Айкой', 'Айко', 'Айк']
    'business' → ['business']
    """
    patterns = [word]
    # For Cyrillic words >= 5 chars, add stems by trimming 1-2 chars
    if len(word) >= 5 and any('\u0400' <= c <= '\u04ff' for c in word):
        patterns.append(word[:-1])
        patterns.append(word[:-2])
    elif len(word) >= 4 and any('\u0400' <= c <= '\u04ff' for c in word):
        patterns.append(word[:-1])
    return patterns


def _parse_search_query(query: str) -> tuple[str, list[str], list[list[str]]]:
    """Parse search query into (clean_query, tags, keyword_groups).
    - tags: words starting with # (kept as-is for ARRAY overlap)
    - keyword_groups: list of stem groups per original word.
      E.g., ['Айкой', 'отношения'] → [['Айкой','Айко','Айк'], ['отношения','отношени','отношен']]
    - clean_query: original query (for embedding)
    """
    tags = []
    keyword_groups = []
    for word in query.split():
        if word.startswith('#'):
            tags.append(word.lower())
        elif len(word) >= 3 and word.lower() not in _STOP_WORDS:
            keyword_groups.append(_stem_keyword(word))
    return query, tags, keyword_groups


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

        # Parse query for hybrid search
        _, search_tags, keyword_groups = _parse_search_query(query)
        # Flatten for ILIKE and display
        all_keywords = [kw for group in keyword_groups for kw in group]

        # Use hybrid search if tags/keywords detected, else pure semantic
        if search_tags or keyword_groups:
            results = search_hybrid(
                query_embedding, tags=search_tags,
                keywords=all_keywords, keyword_groups=keyword_groups,
                limit=limit,
            )
        else:
            results = search_by_embedding(query_embedding, limit=limit)

        if not results:
            await message.reply_text(f"🔍 По запросу \"{query}\" ничего не найдено.")
            return

        # Format response
        header = f"🔍 Поиск: \"{query}\""
        if search_tags or keyword_groups:
            parts = []
            if search_tags:
                parts.append(f"теги: {' '.join(search_tags)}")
            if keyword_groups:
                originals = [g[0] for g in keyword_groups]
                parts.append(f"слова: {', '.join(originals)}")
            header += f"\n🏷 {' | '.join(parts)}"
        lines = [header + "\n"]
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


async def cluster_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cluster [eps] [min_samples] — run DBSCAN clustering (admin only)."""
    message = update.message
    if update.effective_user.id != ADMIN_USER_ID:
        await message.reply_text("⛔ Нет доступа.")
        return

    # Parse optional params
    args = list(context.args) if context.args else []
    eps = 0.35
    min_samples = 3
    if len(args) >= 1:
        try:
            eps = float(args[0])
        except ValueError:
            await message.reply_text("Использование: /cluster [eps] [min_samples]\nПример: /cluster 0.3 5")
            return
    if len(args) >= 2:
        try:
            min_samples = int(args[1])
        except ValueError:
            pass

    status_msg = await message.reply_text(f"⏳ Кластеризация (eps={eps}, min={min_samples})...")

    try:
        result = run_clustering(eps=eps, min_samples=min_samples)

        lines = [
            f"✅ Кластеризация v{result['version']}:",
            f"  Кластеров: {result['n_clusters']}",
            f"  Шум (без группы): {result['n_noise']}",
            f"  Всего обработано: {result['n_total']}",
            "",
        ]

        if result['clusters']:
            lines.append("Топ-10:")
            for i, c in enumerate(result['clusters'][:10], 1):
                lines.append(f"{i}. [{c['size']}] {c['preview'][:100]}")

        await status_msg.edit_text("\n".join(lines))
    except Exception as e:
        logger.error(f"Cluster error: {e}")
        await status_msg.edit_text(f"❌ Ошибка кластеризации: {e}")


async def chains_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chains [N] — show top N clusters of latest version."""
    message = update.message

    # Parse optional limit
    args = list(context.args) if context.args else []
    limit = 10
    if args and args[0].isdigit():
        limit = min(int(args[0]), 30)

    version = get_latest_cluster_version()
    if version is None:
        await message.reply_text("Кластеров пока нет. Запусти /cluster")
        return

    clusters = get_clusters_by_version(version)
    if not clusters:
        await message.reply_text("Кластеров пока нет. Запусти /cluster")
        return

    lines = [f"📊 Кластеры (v{version}, {len(clusters)} шт.):\n"]
    for i, c in enumerate(clusters[:limit], 1):
        preview = c['preview'][:100] if c['preview'] else "—"
        lines.append(f"{i}. #{c['id']} [{c['size']} фр.] {preview}")

    await message.reply_text("\n".join(lines))


async def chain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chain N [page] — show fragments of cluster #N."""
    message = update.message
    args = list(context.args) if context.args else []

    if not args or not args[0].isdigit():
        await message.reply_text("Использование: /chain <cluster_id> [страница]\nПример: /chain 12")
        return

    cluster_id = int(args[0])
    page = 1
    if len(args) >= 2 and args[1].isdigit():
        page = max(1, int(args[1]))

    per_page = 10
    offset = (page - 1) * per_page

    fragments = get_cluster_fragments(cluster_id, limit=per_page, offset=offset)
    if not fragments:
        await message.reply_text(f"Кластер #{cluster_id} не найден или пуст.")
        return

    # Get cluster info for header
    version = get_latest_cluster_version()
    clusters = get_clusters_by_version(version) if version else []
    cluster_info = next((c for c in clusters if c['id'] == cluster_id), None)
    total = cluster_info['size'] if cluster_info else len(fragments)

    lines = [f"🔗 Кластер #{cluster_id} ({total} фрагментов):\n"]
    for i, f in enumerate(fragments, offset + 1):
        date = f['created_at'][:10] if f['created_at'] else "?"
        text_preview = f['text'][:120].replace('\n', ' ')
        if len(f['text']) > 120:
            text_preview += "..."
        link = _make_telegram_link(f.get('external_id'))

        line = f"{i}. {date}\n   {text_preview}"
        if link:
            line += f"\n   {link}"
        lines.append(line)

    total_pages = (total + per_page - 1) // per_page
    if total_pages > 1:
        lines.append(f"\n[стр. {page}/{total_pages}, /chain {cluster_id} {page + 1} — след.]")

    await message.reply_text("\n\n".join(lines), disable_web_page_preview=True)
