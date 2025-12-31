"""
Facility Terminal Mapping Model

Maps EDC terminals to facilities with status and color coding.
"""

from sqlalchemy import Column, Integer, String, Boolean, Index
from app.models.common import CommonModel


class FacilityTerminal(CommonModel):
    """
    Maps EDC terminals to facilities with status and color information.
    
    Attributes:
        facility_code: Facility identifier (e.g., "FAC001")
        terminal_id: EDC terminal ID (e.g., "70002030")
        terminal_name: Human-readable terminal name (e.g., "Counter 1")
        status: Terminal status (ACTIVE, INACTIVE, MAINTENANCE)
        color_hex: Hex color code for UI display (e.g., "#FF5733")
        is_active: Boolean flag for quick filtering
    """
    __tablename__ = "facility_terminals"

    id = Column(Integer, primary_key=True, index=True)
    facility_code = Column(String(100), nullable=False, index=True)
    terminal_id = Column(String(50), nullable=False, index=True)
    terminal_name = Column(String(255), nullable=True)
    status = Column(String(50), default="ACTIVE", nullable=False)  # ACTIVE, INACTIVE, MAINTENANCE
    color_hex = Column(String(7), default="#4CAF50", nullable=False)  # Default green
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    merchant_id = Column(String(100), nullable=True)
    merchant_key = Column(String(255), nullable=True)

    # Composite index for facility + terminal lookup
    __table_args__ = (
        Index("idx_facility_terminal", "facility_code", "terminal_id", unique=True),
        Index("idx_facility_active", "facility_code", "is_active"),
    )

    def __repr__(self):
        return f"<FacilityTerminal(facility={self.facility_code}, terminal={self.terminal_id}, status={self.status}, color={self.color_hex})>"
