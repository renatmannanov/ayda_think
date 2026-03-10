"""
Normalizer Service — embeddings, language detection, deduplication.
Processes fragments that have no embedding yet.
"""
import logging
from services.transcription_service import get_openai_client
from storage.fragments_db import (
    get_unembedded_fragments,
    get_fragments_by_ids,
    update_embedding,
    update_fragment_fields,
    find_near_duplicates,
)

logger = logging.getLogger(__name__)


def normalize_all(batch_size: int = 50) -> dict:
    """Run normalization on all unembedded fragments.
    Commits to DB after each batch so progress is not lost on error.
    Returns: {embedded: N, duplicates: N, errors: N}
    """
    embedded = 0
    duplicates = 0
    errors = 0

    while True:
        fragments = get_unembedded_fragments(limit=batch_size)
        if not fragments:
            break

        batch_result = _process_batch(fragments)
        embedded += batch_result['embedded']
        duplicates += batch_result['duplicates']
        errors += batch_result['errors']

        logger.info(f"Batch done: +{batch_result['embedded']} embedded, "
                     f"+{batch_result['duplicates']} duplicates, "
                     f"+{batch_result['errors']} errors")

    logger.info(f"Normalization complete: {embedded} embedded, "
                f"{duplicates} duplicates, {errors} errors")
    return {'embedded': embedded, 'duplicates': duplicates, 'errors': errors}


def normalize_fragments(fragment_ids: list[int]) -> dict:
    """Normalize specific fragments (for auto-normalization after insert).
    Returns: {embedded: N, duplicates: N, errors: N}
    """
    if not fragment_ids:
        return {'embedded': 0, 'duplicates': 0, 'errors': 0}

    fragments = get_fragments_by_ids(fragment_ids)
    if not fragments:
        return {'embedded': 0, 'duplicates': 0, 'errors': 0}

    return _process_batch(fragments)


def _process_batch(fragments: list[dict]) -> dict:
    """Process a batch: generate embeddings, detect language, check duplicates."""
    embedded = 0
    duplicates = 0
    errors = 0

    try:
        embeddings = _generate_embeddings(fragments)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return {'embedded': 0, 'duplicates': 0, 'errors': len(fragments)}

    for frag, emb in zip(fragments, embeddings):
        try:
            # Save embedding
            update_embedding(frag['id'], emb)

            # Detect language
            language = _detect_language(frag['text'])
            update_fragment_fields(frag['id'], language=language)

            # Check duplicates
            if _check_duplicates(frag['id'], emb):
                duplicates += 1
            else:
                embedded += 1
        except Exception as e:
            logger.error(f"Error processing fragment {frag['id']}: {e}")
            errors += 1

    return {'embedded': embedded, 'duplicates': duplicates, 'errors': errors}


def _generate_embeddings(fragments: list[dict]) -> list[list[float]]:
    """Batch request to OpenAI text-embedding-3-small."""
    client = get_openai_client()
    texts = [f['text'] for f in fragments]

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )

    return [item.embedding for item in response.data]


def _detect_language(text: str) -> str:
    """Detect language by letter characters (no API call).
    Filters with str.isalpha() — URLs, digits, emojis are ignored.
    > 70% cyrillic → 'ru'
    > 70% latin → 'en'
    Otherwise → 'mixed'
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 'mixed'

    cyrillic = sum(1 for c in letters if '\u0400' <= c <= '\u04ff')
    total = len(letters)
    ratio = cyrillic / total

    if ratio > 0.7:
        return 'ru'
    elif ratio < 0.3:
        return 'en'
    else:
        return 'mixed'


def _check_duplicates(fragment_id: int, embedding: list[float]) -> bool:
    """Check if near-duplicate exists.
    If cosine_similarity > 0.95 with an existing original — mark is_duplicate=True.
    Returns True if duplicate.
    """
    dupes = find_near_duplicates(embedding, threshold=0.95, exclude_id=fragment_id)
    if dupes:
        update_fragment_fields(fragment_id, is_duplicate=True)
        logger.info(f"Fragment {fragment_id} marked as duplicate "
                    f"(similar to {dupes[0]['id']}, distance={dupes[0]['distance']:.4f})")
        return True
    return False
