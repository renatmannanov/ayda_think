"""
Fragment storage: SQLAlchemy models + CRUD for the fragments/clusters/fragment_clusters tables.
Uses pgvector for embedding storage and similarity search when available.
"""

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey,
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
    sender_id = Column(BigInteger, nullable=True)          # Telegram user ID of author
    channel_id = Column(BigInteger, nullable=True)         # Telegram chat ID (-100 format)
    message_thread_id = Column(BigInteger, nullable=True)  # Forum topic ID (1=General)
    if _pgvector_import_ok:
        embedding = Column(Vector(1536), nullable=True)


class Cluster(Base):
    __tablename__ = 'clusters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    label = Column(Integer, nullable=False)
    size = Column(Integer, default=0)
    preview = Column(Text, nullable=True)
    name = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('version', 'label', name='uq_cluster_version_label'),
    )


class FragmentCluster(Base):
    __tablename__ = 'fragment_clusters'

    fragment_id = Column(Integer, ForeignKey('fragments.id'), primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    version = Column(Integer, primary_key=True)


class Artifact(Base):
    __tablename__ = 'artifacts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=True)
    fragment_ids = Column(ARRAY(Integer), default=[])
    created_at = Column(DateTime, default=datetime.utcnow)


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


# ---------------------------------------------------------------------------
# Cluster CRUD
# ---------------------------------------------------------------------------

def get_all_embedded_fragments() -> list[dict]:
    """All fragments with embeddings (excluding duplicates).
    Returns [{id, embedding, tags, text, created_at}, ...].
    """
    if not _pgvector_available():
        logging.warning("get_all_embedded_fragments called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id,
                Fragment.embedding,
                Fragment.tags,
                Fragment.text,
                Fragment.created_at,
            )
            .filter(Fragment.embedding.isnot(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .all()
        )
        return [
            {
                'id': r.id,
                'embedding': list(r.embedding),
                'tags': r.tags or [],
                'text': r.text,
                'created_at': r.created_at,
            }
            for r in results
        ]
    finally:
        session.close()


def get_latest_cluster_version() -> int | None:
    """Max version from clusters table. None if no clusters exist."""
    session = SessionLocal()
    try:
        result = session.query(func.max(Cluster.version)).scalar()
        return result
    finally:
        session.close()


def save_cluster_results(version: int, clusters_data: list[dict]) -> None:
    """Save clustering results in a single transaction.
    clusters_data: [{label, size, preview, fragment_ids}, ...]
    """
    session = SessionLocal()
    try:
        for cd in clusters_data:
            cluster = Cluster(
                version=version,
                label=cd['label'],
                size=cd['size'],
                preview=cd['preview'],
                name=cd.get('name', ''),
            )
            session.add(cluster)
            session.flush()  # get cluster.id

            for fid in cd['fragment_ids']:
                fc = FragmentCluster(
                    fragment_id=fid,
                    cluster_id=cluster.id,
                    version=version,
                )
                session.add(fc)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_clusters_by_version(version: int) -> list[dict]:
    """Clusters for a given version, sorted by size DESC."""
    session = SessionLocal()
    try:
        results = (
            session.query(Cluster)
            .filter(Cluster.version == version)
            .order_by(Cluster.size.desc())
            .all()
        )
        return [
            {
                'id': r.id,
                'label': r.label,
                'size': r.size,
                'preview': r.preview,
                'name': r.name or '',
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]
    finally:
        session.close()


def get_cluster_fragments(cluster_id: int, limit: int = 10, offset: int = 0) -> list[dict]:
    """Fragments of a specific cluster, sorted by created_at.
    Supports pagination via limit/offset.
    """
    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id,
                Fragment.external_id,
                Fragment.text,
                Fragment.tags,
                Fragment.created_at,
            )
            .join(FragmentCluster, FragmentCluster.fragment_id == Fragment.id)
            .filter(FragmentCluster.cluster_id == cluster_id)
            .order_by(Fragment.created_at)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                'id': r.id,
                'external_id': r.external_id,
                'text': r.text,
                'tags': r.tags or [],
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]
    finally:
        session.close()


def get_fragments_clusters(fragment_ids: list[int], version: int) -> dict[int, dict]:
    """Get cluster info for multiple fragments in a single query.

    Returns:
        {fragment_id: {id, label, size, name}, ...}
    """
    if not fragment_ids:
        return {}

    session = SessionLocal()
    try:
        results = (
            session.query(FragmentCluster.fragment_id, Cluster)
            .join(Cluster, Cluster.id == FragmentCluster.cluster_id)
            .filter(FragmentCluster.fragment_id.in_(fragment_ids))
            .filter(FragmentCluster.version == version)
            .all()
        )
        return {
            r.fragment_id: {
                'id': r.Cluster.id,
                'label': r.Cluster.label,
                'size': r.Cluster.size,
                'name': r.Cluster.name or '',
            }
            for r in results
        }
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Artifact CRUD
# ---------------------------------------------------------------------------

def save_artifact(
    topic: str,
    content: str,
    fragment_ids: list[int],
    cluster_id: int | None = None,
) -> int:
    """Save artifact. Returns id."""
    session = SessionLocal()
    try:
        artifact = Artifact(
            topic=topic,
            content=content,
            fragment_ids=fragment_ids,
            cluster_id=cluster_id,
        )
        session.add(artifact)
        session.commit()
        return artifact.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_artifacts_by_cluster(cluster_id: int) -> list[dict]:
    """All artifacts for a cluster."""
    session = SessionLocal()
    try:
        results = (
            session.query(Artifact)
            .filter(Artifact.cluster_id == cluster_id)
            .order_by(Artifact.created_at.desc())
            .all()
        )
        return [_artifact_to_dict(r) for r in results]
    finally:
        session.close()


def get_artifacts_by_topic(topic_query: str, limit: int = 5) -> list[dict]:
    """Search artifacts by topic (ILIKE)."""
    session = SessionLocal()
    try:
        results = (
            session.query(Artifact)
            .filter(Artifact.topic.ilike(f'%{topic_query}%'))
            .order_by(Artifact.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_artifact_to_dict(r) for r in results]
    finally:
        session.close()


def get_latest_artifacts(limit: int = 10) -> list[dict]:
    """Latest artifacts by date."""
    session = SessionLocal()
    try:
        results = (
            session.query(Artifact)
            .order_by(Artifact.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_artifact_to_dict(r) for r in results]
    finally:
        session.close()


def _artifact_to_dict(a: Artifact) -> dict:
    return {
        'id': a.id,
        'topic': a.topic,
        'content': a.content,
        'cluster_id': a.cluster_id,
        'fragment_ids': a.fragment_ids or [],
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }
