"""
OTP Repository

Handles database operations for OTP-related data.
"""

from app.connections.database import execute_raw_sql_readonly
from typing import Dict
from app.logging.utils import get_app_logger

logger = get_app_logger("app.otp_repository")


class OTPRepository:
    """Repository for OTP operations"""

    def get_test_credentials(self) -> Dict[str, str]:
        """
        Get test OTP credentials from database.

        Returns:
            Dict mapping phone numbers to OTP codes for active test records
        """
        try:
            sql = """
                SELECT phone_number, otp
                FROM static_otps
                WHERE is_active = true
            """
            rows = execute_raw_sql_readonly(sql)
            result = {row['phone_number']: row['otp'] for row in rows}
            logger.info(f"get_test_credentials | count={len(result)}")
            return result
        except Exception as e:
            logger.error(f"get_test_credentials_error | error={e}", exc_info=True)
            return {}
