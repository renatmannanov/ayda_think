from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional
import logging
import os

# Base class for models
Base = declarative_base()

class User(Base):
    """User model for storing user-spreadsheet mappings."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    spreadsheet_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChannelMapping(Base):
    """Maps a Telegram channel to a user (channel_id -> user_id)."""
    __tablename__ = 'channel_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChannelMessageMapping(Base):
    """Maps channel post to cloned DM message (for edit sync)."""
    __tablename__ = 'channel_message_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, nullable=False)
    post_id = Column(BigInteger, nullable=False)
    cloned_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database setup — PostgreSQL only (local via docker-compose, prod via Railway)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:localpass@localhost:5433/ayda_think",
)

# Fix for Render/Railway's postgres:// URL (SQLAlchemy requires postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Flag: is pgvector available on this PostgreSQL instance?
pgvector_available = False


def init_db():
    """Initialize database tables. Enables pgvector if available."""
    global pgvector_available

    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        pgvector_available = True
        logging.info("pgvector extension enabled")
    except Exception as e:
        pgvector_available = False
        logging.warning(f"pgvector not available, embedding features disabled: {e}")

    # Import fragment models so they are registered with Base.metadata
    # Must happen AFTER pgvector_available is set
    import storage.fragments_db  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Add 'name' column to clusters table if it doesn't exist
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE clusters ADD COLUMN IF NOT EXISTS name TEXT"
            ))
            conn.commit()
    except Exception as e:
        logging.warning(f"Could not add 'name' column to clusters: {e}")

    # Add source/origin columns to fragments (sender_id, channel_id, message_thread_id)
    # Owned by ayda_think; consumed by telegram-gather API clients for filtering.
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE fragments "
                "ADD COLUMN IF NOT EXISTS sender_id BIGINT, "
                "ADD COLUMN IF NOT EXISTS channel_id BIGINT, "
                "ADD COLUMN IF NOT EXISTS message_thread_id BIGINT"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_fragments_channel_id "
                "ON fragments (channel_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_fragments_sender_id "
                "ON fragments (sender_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_fragments_channel_thread "
                "ON fragments (channel_id, message_thread_id)"
            ))
            conn.commit()
    except Exception as e:
        logging.warning(f"Could not add sender/channel columns to fragments: {e}")

    # Fix NULL booleans: set default values for is_duplicate/is_outdated
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "UPDATE fragments SET is_duplicate = false WHERE is_duplicate IS NULL"
            ))
            conn.execute(text(
                "UPDATE fragments SET is_outdated = false WHERE is_outdated IS NULL"
            ))
            conn.commit()
    except Exception as e:
        logging.warning(f"Could not fix NULL booleans: {e}")

    # Create HNSW index for embeddings (only if pgvector is available)
    if pgvector_available:
        try:
            with engine.connect() as conn:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_fragments_embedding "
                    "ON fragments USING hnsw (embedding vector_cosine_ops)"
                ))
                conn.commit()
            logging.info("HNSW index created for fragments.embedding")
        except Exception as e:
            logging.warning(f"Could not create HNSW index: {e}")

def get_user_spreadsheet(user_id: int) -> Optional[str]:
    """
    Get spreadsheet ID for a user.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        Spreadsheet ID if user exists, None otherwise
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        return user.spreadsheet_id if user else None
    finally:
        session.close()

def get_channel_user(channel_id: int) -> Optional[int]:
    """Get user_id mapped to a channel."""
    session = SessionLocal()
    try:
        mapping = session.query(ChannelMapping).filter(
            ChannelMapping.channel_id == channel_id
        ).first()
        return mapping.user_id if mapping else None
    finally:
        session.close()


def save_channel_mapping(channel_id: int, user_id: int) -> None:
    """Save or update channel -> user mapping."""
    session = SessionLocal()
    try:
        mapping = session.query(ChannelMapping).filter(
            ChannelMapping.channel_id == channel_id
        ).first()
        if mapping:
            mapping.user_id = user_id
        else:
            mapping = ChannelMapping(channel_id=channel_id, user_id=user_id)
            session.add(mapping)
        session.commit()
    finally:
        session.close()


def get_cloned_message_id(channel_id: int, post_id: int) -> Optional[int]:
    """Get cloned DM message_id for a channel post."""
    session = SessionLocal()
    try:
        mapping = session.query(ChannelMessageMapping).filter(
            ChannelMessageMapping.channel_id == channel_id,
            ChannelMessageMapping.post_id == post_id
        ).first()
        return mapping.cloned_id if mapping else None
    finally:
        session.close()


def save_message_mapping(channel_id: int, post_id: int, cloned_id: int) -> None:
    """Save channel post -> cloned DM message mapping."""
    session = SessionLocal()
    try:
        mapping = ChannelMessageMapping(
            channel_id=channel_id, post_id=post_id, cloned_id=cloned_id
        )
        session.add(mapping)
        session.commit()
    finally:
        session.close()


def save_user(user_id: int, spreadsheet_id: str) -> None:
    """
    Save or update user's spreadsheet ID.
    
    Args:
        user_id: Telegram user ID
        spreadsheet_id: Google Sheets spreadsheet ID
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.spreadsheet_id = spreadsheet_id
            user.updated_at = datetime.utcnow()
        else:
            user = User(user_id=user_id, spreadsheet_id=spreadsheet_id)
            session.add(user)
        session.commit()
    finally:
        session.close()
