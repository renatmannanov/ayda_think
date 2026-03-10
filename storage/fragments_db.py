"""
Fragment storage: SQLAlchemy models + CRUD for the fragments/clusters/fragment_clusters tables.
Uses pgvector for embedding storage and similarity search when available.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey,
    UniqueConstraint, func, or_, cast
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from datetime import datetime
from typing import Optional
import logging

import storage.db as _db
from storage.db import Base, SessionLocal

# ---------------------------------------------------------------------------
# Conditional pgvector import
# ---------------------------------------------------------------------------
# Read pgvector_available dynamically from db module (not a copied value)
# because init_db() sets it to True AFTER this module may have been imported.
try:
    from pgvector.sqlalchemy import Vector
    _pgvector_import_ok = True
except ImportError:
    _pgvector_import_ok = False


def _pgvector_available() -> bool:
    """Check if pgvector is available (reads live value from db module)."""
    return _db.pgvector_available and _pgvector_import_ok

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Fragment(Base):
    __tablename__ = 'fragments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=True)
    source = Column(String(50), nullable=False)          # telegram, instagram, linkedin, browser
    text = Column(Text, nullable=False)
    tags = Column(ARRAY(Text), default=[])
    created_at = Column(DateTime, nullable=False)
    indexed_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column('metadata', JSONB, default={})    # 'metadata' is reserved in SQLAlchemy
    content_type = Column(String(20), default='note')    # note / link / quote / repost
    language = Column(String(5), nullable=True)           # ru / en / mixed
    is_duplicate = Column(Boolean, default=False)
    is_outdated = Column(Boolean, default=False)
    if _pgvector_import_ok:
        embedding = Column(Vector(1536), nullable=True)


class Cluster(Base):
    __tablename__ = 'clusters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    label = Column(Integer, nullable=False)
    size = Column(Integer, default=0)
    preview = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('version', 'label', name='uq_cluster_version_label'),
    )


class FragmentCluster(Base):
    __tablename__ = 'fragment_clusters'

    fragment_id = Column(Integer, ForeignKey('fragments.id'), primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    version = Column(Integer, primary_key=True)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def insert_fragment(
    source: str,
    text: str,
    created_at: datetime,
    tags: list[str] | None = None,
    content_type: str = 'note',
    metadata: dict | None = None,
    external_id: str | None = None,
) -> int | None:
    """
    Insert a fragment. Returns fragment id, or None if duplicate (by external_id).
    """
    session = SessionLocal()
    try:
        frag = Fragment(
            external_id=external_id,
            source=source,
            text=text,
            created_at=created_at,
            tags=tags or [],
            content_type=content_type,
            metadata_=metadata or {},
        )
        session.add(frag)
        session.commit()
        return frag.id
    except Exception:
        session.rollback()
        return None
    finally:
        session.close()


def insert_fragments_batch(fragments: list[dict]) -> dict:
    """
    Insert multiple fragments. Skips duplicates by external_id.
    Returns {'indexed': N, 'duplicates_skipped': N, 'inserted_ids': [int]}.
    """
    session = SessionLocal()
    indexed = 0
    skipped = 0
    inserted_ids = []
    try:
        for f in fragments:
            # Check duplicate by external_id
            if f.get('external_id'):
                exists = session.query(Fragment.id).filter(
                    Fragment.external_id == f['external_id']
                ).first()
                if exists:
                    skipped += 1
                    continue

            frag = Fragment(
                external_id=f.get('external_id'),
                source=f['source'],
                text=f['text'],
                created_at=f['created_at'],
                tags=f.get('tags', []),
                content_type=f.get('content_type', 'note'),
                metadata_=f.get('metadata', {}),
            )
            session.add(frag)
            session.flush()  # get frag.id before commit
            inserted_ids.append(frag.id)
            indexed += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {'indexed': indexed, 'duplicates_skipped': skipped, 'inserted_ids': inserted_ids}


def get_fragments_count() -> int:
    """Total number of fragments."""
    session = SessionLocal()
    try:
        return session.query(func.count(Fragment.id)).scalar()
    finally:
        session.close()


def search_by_embedding(embedding: list[float], limit: int = 10) -> list[dict]:
    """
    Find closest fragments by cosine distance.
    Requires pgvector to be available and embeddings to be set.
    """
    if not _pgvector_available():
        logging.warning("search_by_embedding called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id,
                Fragment.external_id,
                Fragment.text,
                Fragment.source,
                Fragment.tags,
                Fragment.created_at,
                Fragment.content_type,
                Fragment.embedding.cosine_distance(embedding).label('distance')
            )
            .filter(Fragment.embedding.isnot(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .order_by('distance')
            .limit(limit)
            .all()
        )
        return [
            {
                'id': r.id,
                'external_id': r.external_id,
                'text': r.text,
                'source': r.source,
                'tags': r.tags,
                'created_at': r.created_at.isoformat(),
                'content_type': r.content_type,
                'distance': float(r.distance),
            }
            for r in results
        ]
    finally:
        session.close()


def search_by_keywords(
    tags: list[str] | None = None,
    keywords: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Find fragments matching tags (ARRAY overlap) and/or keywords (ILIKE on text).
    Returns same dict shape as search_by_embedding but without distance.
    """
    if not tags and not keywords:
        return []

    session = SessionLocal()
    try:
        query = session.query(
            Fragment.id,
            Fragment.external_id,
            Fragment.text,
            Fragment.source,
            Fragment.tags,
            Fragment.created_at,
            Fragment.content_type,
        ).filter(Fragment.is_duplicate.isnot(True))

        conditions = []
        if tags:
            conditions.append(Fragment.tags.overlap(tags))
        if keywords:
            conditions.extend(
                Fragment.text.ilike(f'%{kw}%') for kw in keywords
            )
        query = query.filter(or_(*conditions))
        query = query.order_by(Fragment.created_at.desc()).limit(limit)

        results = query.all()
        return [
            {
                'id': r.id,
                'external_id': r.external_id,
                'text': r.text,
                'source': r.source,
                'tags': r.tags,
                'created_at': r.created_at.isoformat(),
                'content_type': r.content_type,
                'distance': None,
            }
            for r in results
        ]
    finally:
        session.close()


def search_hybrid(
    embedding: list[float],
    tags: list[str] | None = None,
    keywords: list[str] | None = None,
    keyword_groups: list[list[str]] | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Hybrid search: semantic + keyword/tag matching.
    Runs both searches, merges by id, re-ranks with combined scoring.

    keyword_groups: list of stem groups per original word, e.g.
      [['Айкой','Айко','Айк'], ['отношения','отношени','отношен']]
    Used to calculate what fraction of original words matched each fragment.
    """
    semantic_results = search_by_embedding(embedding, limit=limit * 2)
    keyword_results = search_by_keywords(tags, keywords, limit=limit * 2)

    # Build lookup: id -> result dict
    merged = {}
    for r in semantic_results:
        merged[r['id']] = {**r, '_semantic': True, '_keyword': False}
    for r in keyword_results:
        if r['id'] in merged:
            merged[r['id']]['_keyword'] = True
        else:
            merged[r['id']] = {**r, '_semantic': False, '_keyword': True}

    # Count how many original words each fragment matches
    groups = keyword_groups or []
    total_words = len(groups) + (len(tags) if tags else 0)

    # Score and rank
    scored = []
    for fid, r in merged.items():
        if r['_semantic'] and r['distance'] is not None:
            semantic_score = 1.0 - r['distance']
        else:
            semantic_score = 0.0

        # Count matched word groups
        matched = 0
        if tags and r['tags']:
            for t in tags:
                if t in r['tags']:
                    matched += 1
        text_lower = r['text'].lower()
        for group in groups:
            if any(stem.lower() in text_lower for stem in group):
                matched += 1

        # Bonus proportional to fraction of words matched
        if total_words > 0 and matched > 0:
            keyword_bonus = 0.7 * (matched / total_words)
        else:
            keyword_bonus = 0.0

        final_score = semantic_score * 0.4 + keyword_bonus
        r['distance'] = round(1.0 - final_score, 4)
        scored.append((final_score, r))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [r for _, r in scored[:limit]]


def get_unembedded_fragments(limit: int = 100) -> list[dict]:
    """Get fragments without embeddings (embedding IS NULL, is_duplicate=False)."""
    if not _pgvector_available():
        logging.warning("get_unembedded_fragments called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        results = (
            session.query(Fragment.id, Fragment.text)
            .filter(Fragment.embedding.is_(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .limit(limit)
            .all()
        )
        return [{'id': r.id, 'text': r.text} for r in results]
    finally:
        session.close()


def update_embedding(fragment_id: int, embedding: list[float]) -> None:
    """Save embedding for a fragment."""
    session = SessionLocal()
    try:
        session.query(Fragment).filter(Fragment.id == fragment_id).update(
            {Fragment.embedding: embedding}
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_fragment_fields(fragment_id: int, **fields) -> None:
    """Update arbitrary fields (language, is_duplicate, is_outdated)."""
    session = SessionLocal()
    try:
        session.query(Fragment).filter(Fragment.id == fragment_id).update(
            {getattr(Fragment, k): v for k, v in fields.items()}
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def find_near_duplicates(
    embedding: list[float],
    threshold: float = 0.95,
    exclude_id: int | None = None,
) -> list[dict]:
    """Find fragments with cosine similarity > threshold.
    Only compares against originals (is_duplicate=False).
    """
    if not _pgvector_available():
        logging.warning("find_near_duplicates called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        query = (
            session.query(
                Fragment.id,
                Fragment.text,
                Fragment.embedding.cosine_distance(embedding).label('distance')
            )
            .filter(Fragment.embedding.isnot(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .filter(
                Fragment.embedding.cosine_distance(embedding) < (1 - threshold)
            )
        )
        if exclude_id is not None:
            query = query.filter(Fragment.id != exclude_id)

        results = query.order_by('distance').all()
        return [
            {'id': r.id, 'text': r.text, 'distance': float(r.distance)}
            for r in results
        ]
    finally:
        session.close()


def get_fragments_by_ids(fragment_ids: list[int]) -> list[dict]:
    """Get fragments by list of IDs."""
    session = SessionLocal()
    try:
        results = (
            session.query(Fragment.id, Fragment.text)
            .filter(Fragment.id.in_(fragment_ids))
            .all()
        )
        return [{'id': r.id, 'text': r.text} for r in results]
    finally:
        session.close()
