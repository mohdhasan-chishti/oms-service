"""
DTOs for Facility Terminal API
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TerminalInfo(BaseModel):
    """Terminal information with status and color"""
    id: int
    facility_code: str
    terminal_id: str
    terminal_name: Optional[str] = None
    status: str = Field(..., description="Terminal status: ACTIVE, INACTIVE, MAINTENANCE")
    color_hex: str = Field(..., description="Hex color code for UI (e.g., #FF5733)")
    is_active: bool

    class Config:
        from_attributes = True


class FacilityTerminalsResponse(BaseModel):
    """Response with list of terminals for a facility"""
    success: bool
    facility_code: str
    terminal_count: int
    terminals: List[TerminalInfo]

    class Config:
        from_attributes = True


