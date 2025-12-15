import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from dotenv import load_dotenv

# Load environment variables from .env file
# Assuming .env is in the backend root directory (../../..)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback or error if not found
    raise ValueError("DATABASE_URL not found in .env file")

# Create engine
# pool_recycle to prevent MySQL connection timeout
engine = create_engine(DATABASE_URL, pool_recycle=3600, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Scoped session for thread safety in web apps
db_session = scoped_session(SessionLocal)

# Base class for models
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    """Initialize database tables"""
    import src.crawl.infrastructure.database.models
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for getting DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
