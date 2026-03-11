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
from services.synthesis_service import synthesize
from storage.fragments_db import (
    search_by_embedding, search_hybrid, get_fragments_count,
    get_latest_cluster_version, get_fragments_clusters,
    get_cluster_fragments, save_artifact,
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

        # Get cluster info for results
        version = get_latest_cluster_version()
        cluster_map = {}
        if version and results:
            frag_ids = [r['id'] for r in results]
            cluster_map = get_fragments_clusters(frag_ids, version)

        # Count results per cluster for grouping
        cluster_counts = {}
        for r in results:
            cl = cluster_map.get(r['id'])
            if cl:
                cluster_counts[cl['id']] = cluster_counts.get(cl['id'], 0) + 1

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

        rendered_clusters = set()
        idx = 1
        for r in results:
            cl = cluster_map.get(r['id'])
            cl_id = cl['id'] if cl else None

            # Group: >= 2 results from same cluster
            if cl and cluster_counts.get(cl_id, 0) >= 2:
                if cl_id in rendered_clusters:
                    continue  # already rendered as group
                rendered_clusters.add(cl_id)

                cl_name = cl['name'] or cl['label']
                lines.append(f"📦 {cl_name} ({cl['size']} фр., /chain {cl_id})")
                for item in results:
                    item_cl = cluster_map.get(item['id'])
                    if not item_cl or item_cl['id'] != cl_id:
                        continue
                    date = item['created_at'][:10]
                    text_preview = item['text'][:120].replace('\n', ' ')
                    if len(item['text']) > 120:
                        text_preview += "..."
                    distance = f"[{item['distance']:.2f}]"
                    link = _make_telegram_link(item.get('external_id'))
                    line = f"  {idx}. {distance} {date}\n     {text_preview}"
                    if link:
                        line += f"\n     {link}"
                    lines.append(line)
                    idx += 1
            else:
                # Single result (with or without cluster)
                date = r['created_at'][:10]
                text_preview = r['text'][:120].replace('\n', ' ')
                if len(r['text']) > 120:
                    text_preview += "..."
                distance = f"[{r['distance']:.2f}]"
                link = _make_telegram_link(r.get('external_id'))

                cl_tag = ""
                if cl:
                    cl_tag = f" 📦{(cl['name'] or str(cl['label']))[:30]}"
                line = f"{idx}. {distance} {date}{cl_tag}"
                line += f"\n   {text_preview}"
                if link:
                    line += f"\n   {link}"
                lines.append(line)
                idx += 1

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
    """Handle /cluster [min_cluster_size] [min_samples] — run HDBSCAN clustering (admin only)."""
    message = update.message
    if update.effective_user.id != ADMIN_USER_ID:
        await message.reply_text("⛔ Нет доступа.")
        return

    # Parse optional params
    args = list(context.args) if context.args else []
    min_cluster_size = 5
    min_samples = 3
    if len(args) >= 1:
        try:
            min_cluster_size = int(args[0])
        except ValueError:
            await message.reply_text("Использование: /cluster [min_cluster_size] [min_samples]\nПример: /cluster 5 3")
            return
    if len(args) >= 2:
        try:
            min_samples = int(args[1])
        except ValueError:
            pass

    status_msg = await message.reply_text(f"⏳ Кластеризация (min_size={min_cluster_size}, min_samples={min_samples})...\nГенерация AI-имён может занять ~20 сек.")

    try:
        result = run_clustering(min_cluster_size=min_cluster_size, min_samples=min_samples)

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
                name = c.get('name', '')
                display = name if name else c['preview'][:100]
                lines.append(f"{i}. [{c['size']}] {display}")

        await status_msg.edit_text("\n".join(lines))
    except Exception as e:
        logger.error(f"Cluster error: {e}")
        await status_msg.edit_text(f"❌ Ошибка кластеризации: {e}")


async def artifact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /artifact [topic] — GPT synthesis of thought evolution."""
    message = update.message
    topic = " ".join(context.args) if context.args else ""

    if not topic:
        await message.reply_text(
            "Использование: /artifact <тема>\n"
            "Пример: /artifact чайный бизнес"
        )
        return

    status_msg = await message.reply_text(f"⏳ Анализирую тему «{topic}»...")

    try:
        # 1. Embed query
        client = get_openai_client()
        resp = client.embeddings.create(model="text-embedding-3-small", input=topic)
        query_embedding = resp.data[0].embedding

        # 2. Hybrid search (more results than /search)
        _, search_tags, keyword_groups = _parse_search_query(topic)
        all_keywords = [kw for group in keyword_groups for kw in group]

        if search_tags or keyword_groups:
            search_results = search_hybrid(
                query_embedding, tags=search_tags,
                keywords=all_keywords, keyword_groups=keyword_groups,
                limit=30,
            )
        else:
            search_results = search_by_embedding(query_embedding, limit=30)

        if not search_results:
            await status_msg.edit_text(f"🔍 По теме «{topic}» ничего не найдено.")
            return

        # 3. Cluster context: pull all fragments from relevant clusters
        version = get_latest_cluster_version()
        primary_cluster_id = None
        primary_cluster_name = None
        all_fragments = {r['id']: r for r in search_results}

        if version:
            frag_ids = [r['id'] for r in search_results]
            cluster_map = get_fragments_clusters(frag_ids, version)

            # Find the most common cluster among search results
            cluster_counts = {}
            for fid, cl in cluster_map.items():
                cluster_counts[cl['id']] = cluster_counts.get(cl['id'], 0) + 1

            if cluster_counts:
                primary_cluster_id = max(cluster_counts, key=cluster_counts.get)
                primary_cluster_name = cluster_map[
                    next(fid for fid, cl in cluster_map.items() if cl['id'] == primary_cluster_id)
                ]['name']

                # Pull all fragments from primary cluster
                cluster_frags = get_cluster_fragments(primary_cluster_id, limit=500)
                for cf in cluster_frags:
                    if cf['id'] not in all_fragments:
                        all_fragments[cf['id']] = cf

        # 4. Sort by date
        fragments = sorted(all_fragments.values(), key=lambda f: f.get('created_at', ''))

        await status_msg.edit_text(
            f"⏳ Анализирую тему «{topic}»...\n"
            f"📊 Найдено {len(fragments)} заметок"
            + (f" (кластер «{primary_cluster_name}»)" if primary_cluster_name else "")
        )

        # 5. Synthesize
        result = synthesize(topic, fragments)

        # 6. Save artifact
        artifact_id = save_artifact(
            topic=topic,
            content=result['content'],
            fragment_ids=result['fragment_ids'],
            cluster_id=primary_cluster_id,
        )

        # 7. Format and send response
        header = f"🧬 Артефакт #{artifact_id}: «{topic}»"
        meta_parts = [f"{len(result['fragment_ids'])} заметок"]
        if primary_cluster_name:
            meta_parts.append(f"📦 {primary_cluster_name}")
        header += f"\n📊 {' | '.join(meta_parts)}\n"

        full_text = header + "\n" + result['content']

        # Split if > 4096 chars (Telegram limit)
        await _send_long_message(status_msg, full_text)

    except Exception as e:
        logger.error(f"Artifact error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка: {e}")


async def _send_long_message(status_msg, text: str, max_len: int = 4096):
    """Send text, splitting into multiple messages if needed."""
    if len(text) <= max_len:
        await status_msg.edit_text(text)
        return

    # First chunk: edit the status message
    chunks = _split_text(text, max_len)
    await status_msg.edit_text(chunks[0])

    # Remaining chunks: send as new messages
    chat_id = status_msg.chat_id
    for chunk in chunks[1:]:
        await status_msg.get_bot().send_message(chat_id=chat_id, text=chunk)


def _split_text(text: str, max_len: int = 4096) -> list[str]:
    """Split text into chunks, preferring line breaks."""
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Find last newline before max_len
        split_at = text.rfind('\n', 0, max_len)
        if split_at == -1 or split_at < max_len // 2:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    return chunks
