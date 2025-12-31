"""
Facility Terminal API endpoints for POS system.
Provides GET endpoint to retrieve available terminals for a facility.
"""

from fastapi import APIRouter, HTTPException, Query
from app.repository.facility_terminal import FacilityTerminalRepository
from app.dto.facility_terminal import FacilityTerminalsResponse, TerminalInfo

from app.logging.utils import get_app_logger
logger = get_app_logger('pos.facility_terminals')

facility_terminal_router = APIRouter(tags=["pos-facility-terminals"])


@facility_terminal_router.get("/terminals")
async def get_terminals(facility_code: str = Query(..., description="Facility identifier")):
    """
    Query Parameters:
        facility_code: Facility identifier (e.g., "FAC001")

    Returns:
        List of terminals with status and color information
    """
    try:
        repo = FacilityTerminalRepository()
        terminals = repo.get_terminals_by_facility(facility_code)

        if not terminals:
            logger.warning(f"no_terminals_found | facility_code={facility_code}")
            raise HTTPException(status_code=404, detail=f"No terminals found for facility {facility_code}")

        terminal_list = []
        for terminal in terminals:
            terminal_list.append(TerminalInfo(**dict(terminal)))

        response = FacilityTerminalsResponse(
            success=True,
            facility_code=facility_code,
            terminal_count=len(terminal_list),
            terminals=terminal_list
        )

        logger.info(f"get_terminals_success | facility_code={facility_code} count={len(terminal_list)}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_terminals_error | facility_code={facility_code} error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve terminals")
