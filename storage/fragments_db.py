"""
Fragment storage: SQLAlchemy models + CRUD for the fragments/clusters/fragment_clusters tables.
Uses pgvector for embedding storage and similarity search.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey,
    UniqueConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector
from datetime import datetime
from typing import Optional

from storage.db import Base, SessionLocal

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Fragment(Base):
    __tablename__ = 'fragments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=True)
    source = Column(String(50), nullable=False)          # telegram, instagram, linkedin, browser
    text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)      # OpenAI text-embedding-3-small
    tags = Column(ARRAY(Text), default=[])
    created_at = Column(DateTime, nullable=False)
    indexed_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column('metadata', JSONB, default={})    # 'metadata' is reserved in SQLAlchemy
    content_type = Column(String(20), default='note')    # note / link / quote / repost
    language = Column(String(5), nullable=True)           # ru / en / mixed
    is_duplicate = Column(Boolean, default=False)
    is_outdated = Column(Boolean, default=False)


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
    Returns {'indexed': N, 'duplicates_skipped': N}.
    """
    session = SessionLocal()
    indexed = 0
    skipped = 0
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
            indexed += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {'indexed': indexed, 'duplicates_skipped': skipped}


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
    Requires embedding to be set on fragments.
    """
    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id,
                Fragment.text,
                Fragment.source,
                Fragment.tags,
                Fragment.created_at,
                Fragment.content_type,
                Fragment.embedding.cosine_distance(embedding).label('distance')
            )
            .filter(Fragment.embedding.isnot(None))
            .filter(Fragment.is_duplicate.is_(False))
            .order_by('distance')
            .limit(limit)
            .all()
        )
        return [
            {
                'id': r.id,
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
