"""
SQLAlchemy ORM Database Configuration
Lets SQLAlchemy manage connections internally with built-in pooling.
Use this for internal/small queries, while keeping raw SQL for high-traffic customer APIs.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Generator, Any, Dict, List
from contextlib import contextmanager


# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("database")

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

# Database URLs - Convert postgresql:// to postgresql+psycopg:// for psycopg3 driver
DATABASE_URL = configs.DATABASE_URL
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

DATABASE_READ_URL = configs.DATABASE_READ_URL
if DATABASE_READ_URL and DATABASE_READ_URL.startswith("postgresql://"):
    DATABASE_READ_URL = DATABASE_READ_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Base class for ORM models
Base = declarative_base()

# Create engines with built-in connection pooling
# SQLAlchemy handles all connection management internally
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # Number of connections to maintain in pool
    max_overflow=20,        # Additional connections beyond pool_size
    pool_pre_ping=True,     # Validate connections before use
    pool_recycle=3600,      # Recycle connections after 1 hour
    echo=False,             # Set to True for SQL query logging
    connect_args={
        "keepalives_idle": 600,
        "keepalives_interval": 30,
        "keepalives_count": 3
    }
)

# Read engine (separate for read replicas, same as write if no replica)
read_engine = create_engine(
    DATABASE_READ_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
    connect_args={
        "keepalives_idle": 600,
        "keepalives_interval": 30,
        "keepalives_count": 3
    }
) if DATABASE_READ_URL != DATABASE_URL else engine

# Session makers - SQLAlchemy manages session lifecycle
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=read_engine)

# FastAPI dependency for database sessions
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for write database sessions.
    SQLAlchemy automatically manages connection pooling and lifecycle.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_read_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for read-only database sessions.
    SQLAlchemy automatically manages connection pooling and lifecycle.
    """
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Optional: For service layer usage (not FastAPI dependencies)
class DatabaseSession:
    """Simple database session manager for service layer"""
    
    @staticmethod
    def get_session() -> Session:
        """Get a new database session - remember to close it!"""
        return SessionLocal()
    
    @staticmethod
    def get_read_session() -> Session:
        """Get a new read-only database session - remember to close it!"""
        return ReadSessionLocal()

logger.info("SQLAlchemy engines initialized with built-in connection pooling")

# Simplified raw SQL execution using SessionLocal
def execute_raw_sql(query: str, params: Dict[str, Any] = None, fetch_results: bool = True) -> List[Dict[str, Any]]:
    """
    Execute raw SQL query using SessionLocal.
    Use this for high-performance customer-facing APIs.
    
    Args:
        query: SQL query string
        params: Query parameters (optional)
        fetch_results: Whether to fetch and return results
    
    Returns:
        List of dictionaries representing query results
    """
    db = SessionLocal()
    try:
        result = db.execute(text(query), params or {})
        if fetch_results:
            # Convert result to list of dictionaries
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
        db.commit()
        return []
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def execute_raw_sql_readonly(query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Execute raw SQL read-only query using read SessionLocal.
    Use this for high-performance read operations.
    
    Args:
        query: SQL query string
        params: Query parameters (optional)
    
    Returns:
        List of dictionaries representing query results
    """
    db = ReadSessionLocal()
    try:
        result = db.execute(text(query), params or {})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        db.close()

@contextmanager
def get_db_session(read_only: bool = False):
    """
    Get database session for complex operations with transaction management.
    Use this when you need transaction control or multiple queries.
    
    Args:
        read_only: Whether to use read-only session
    
    Yields:
        SQLAlchemy session object
    """
    session_class = ReadSessionLocal if read_only else SessionLocal
    db = session_class()
    try:
        yield db
        if not read_only:
            db.commit()
    except Exception:
        if not read_only:
            db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_raw_transaction():
    """
    Get database session with transaction management for raw SQL operations.
    Use this for complex raw SQL operations that need transactions.
    
    Yields:
        SQLAlchemy session object with active transaction
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def close_db_pool():
    engine.dispose()
    read_engine.dispose()
