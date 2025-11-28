from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional
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
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, spreadsheet_id={self.spreadsheet_id})>"

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ayda_think.db")

# Fix for Render's postgres:// URL (SQLAlchemy requires postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

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
