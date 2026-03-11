"""
Synthesis Service — two-pass GPT engine for thought evolution analysis.

Pass 1 (selection): if fragments > 30, GPT selects 15-20 most relevant.
Pass 2 (synthesis): GPT analyzes evolution, turns, contradictions, next steps.
"""
import logging
from services.transcription_service import get_openai_client

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
MAX_FRAGMENTS_WITHOUT_SELECTION = 30
SELECTION_TARGET = 20

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SELECTION_PROMPT = """Тебе дан список заметок одного человека. Тема анализа: "{topic}".

Выбери {target} самых релевантных заметок для анализа этой темы.
Верни ТОЛЬКО номера (id) через запятую, без пояснений.

Заметки:
{fragments_list}"""

SYNTHESIS_PROMPT = """Ты анализируешь заметки одного человека по теме "{topic}".
Заметки упорядочены по дате от ранних к поздним.

Задача — НЕ пересказывать, а найти:
1. Как менялось мышление по этой теме со временем
2. Ключевые повороты и точки перелома
3. Противоречия (если есть)
4. Куда может двигаться мысль дальше

Правила:
- Опирайся ТОЛЬКО на предоставленные заметки
- Каждый вывод подкрепляй ссылкой на конкретную заметку [#N]
- Если данных недостаточно для вывода — скажи об этом
- Не додумывай то, чего нет в заметках
- Пиши на русском
- Будь конкретным и лаконичным

Заметки:
{fragments_text}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def synthesize(topic: str, fragments: list[dict]) -> dict:
    """
    Two-pass GPT synthesis.

    Args:
        topic: analysis topic
        fragments: [{id, text, created_at, tags}, ...] sorted by date

    Returns:
        {
            'content': str,           # GPT response
            'fragment_ids': list[int], # which fragments were used
            'model': str,
        }
    """
    if len(fragments) < 3:
        return {
            'content': _insufficient_data_message(topic, fragments),
            'fragment_ids': [f['id'] for f in fragments],
            'model': MODEL,
        }

    # Pass 1: selection (if too many fragments)
    if len(fragments) > MAX_FRAGMENTS_WITHOUT_SELECTION:
        logger.info(f"Pass 1: selecting {SELECTION_TARGET} from {len(fragments)} fragments")
        selected_ids = _select_fragments(topic, fragments)
        selected = [f for f in fragments if f['id'] in selected_ids]
        # Keep date order
        selected.sort(key=lambda f: f['created_at'])
        logger.info(f"Pass 1 done: selected {len(selected)} fragments")
    else:
        selected = fragments

    # Pass 2: synthesis
    logger.info(f"Pass 2: synthesizing {len(selected)} fragments on topic '{topic}'")
    content = _synthesize_fragments(topic, selected)

    return {
        'content': content,
        'fragment_ids': [f['id'] for f in selected],
        'model': MODEL,
    }


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _select_fragments(topic: str, fragments: list[dict]) -> set[int]:
    """Pass 1: GPT selects most relevant fragment IDs."""
    fragments_list = "\n".join(
        f"[{f['id']}] {f['created_at'][:10]} — {f['text'][:100]}"
        for f in fragments
    )

    prompt = SELECTION_PROMPT.format(
        topic=topic,
        target=SELECTION_TARGET,
        fragments_list=fragments_list,
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()
    logger.debug(f"Selection raw response: {raw}")

    # Parse comma-separated IDs
    valid_ids = {f['id'] for f in fragments}
    selected = set()
    for token in raw.replace('\n', ',').split(','):
        token = token.strip().strip('[]#')
        try:
            fid = int(token)
            if fid in valid_ids:
                selected.add(fid)
        except ValueError:
            continue

    # Fallback: if GPT returned too few, use all
    if len(selected) < 5:
        logger.warning(f"Selection returned only {len(selected)} IDs, using all fragments")
        return {f['id'] for f in fragments}

    return selected


def _synthesize_fragments(topic: str, fragments: list[dict]) -> str:
    """Pass 2: GPT analyzes thought evolution."""
    fragments_text = "\n\n".join(
        f"[#{f['id']}] ({f['created_at'][:10]})\n{f['text']}"
        for f in fragments
    )

    prompt = SYNTHESIS_PROMPT.format(
        topic=topic,
        fragments_text=fragments_text,
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()


def _insufficient_data_message(topic: str, fragments: list[dict]) -> str:
    """Fallback when too few fragments for analysis."""
    lines = [f"По теме «{topic}» найдено только {len(fragments)} заметок — недостаточно для анализа.\n"]
    for f in fragments:
        lines.append(f"• ({f['created_at'][:10]}) {f['text'][:150]}")
    return "\n".join(lines)
