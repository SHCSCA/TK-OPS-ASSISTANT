from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import config
from pathlib import Path

# Ensure DB directory exists
if not config.ASSET_LIBRARY_DIR.exists():
    config.ASSET_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = config.ASSET_LIBRARY_DIR / "assets.db"
# SQLite URL
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False allows sharing connection across threads (careful with writes transaction lock)
# SQLite supports one writer at a time, but allowing connection sharing avoids "ProgrammingError" in readers.
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False, "timeout": 15}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency for getting a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
