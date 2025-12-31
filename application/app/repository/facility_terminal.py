"""
Facility Terminal Repository

Handles database operations for facility-terminal mappings.
"""

from app.connections.database import execute_raw_sql_readonly
from typing import Dict, Any, List
from app.logging.utils import get_app_logger

logger = get_app_logger("app.facility_terminal_repository")


class FacilityTerminalRepository:
    """Repository for facility-terminal mapping operations"""

    def get_terminals_by_facility(self, facility_code: str) -> List[Dict[str, Any]]:
        try:
            query = """
                SELECT id, facility_code, terminal_id, terminal_name, status, color_hex, is_active,
                       created_at, updated_at
                FROM facility_terminals
                WHERE facility_code = :facility_code AND is_active = true
                ORDER BY terminal_name ASC
            """
            rows = execute_raw_sql_readonly(query, {"facility_code": facility_code})
            logger.info(f"get_terminals_by_facility | facility_code={facility_code} count={len(rows) if rows else 0}")
            return rows if rows else []
        except Exception as e:
            logger.error(f"get_terminals_by_facility_error | facility_code={facility_code} error={e}", exc_info=True)
            return []

    def get_terminal_credentials(self, terminal_id: str) -> Dict[str, Any]:
        """Get merchant credentials for Paytm terminal"""
        try:
            query = """
                SELECT merchant_id, merchant_key
                FROM facility_terminals
                WHERE terminal_id = :terminal_id AND is_active = true
                LIMIT 1
            """
            rows = execute_raw_sql_readonly(query, {"terminal_id": terminal_id})
            return dict(rows[0]) if rows else {}
        except Exception as e:
            logger.error(f"get_terminal_credentials_error | terminal_id={terminal_id} error={e}", exc_info=True)
            return {}

