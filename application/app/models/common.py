from sqlalchemy import Column, TIMESTAMP
from sqlalchemy.sql import func
from app.connections.database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def get_ist_now():
    """Get current datetime in IST timezone"""
    return datetime.now(IST)

class CommonModel(Base):
    """Base model with common fields for all models"""
    __abstract__ = True
    
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()    # DB default -> now()
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
        # no onupdate here: rely on DB trigger so raw SQL updates get the timestamp too
    )
