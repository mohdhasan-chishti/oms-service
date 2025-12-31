"""
Selling Price Repository
Handles database queries for selling price mappings
"""

from typing import Optional
from app.connections.database import execute_raw_sql_readonly
from app.logging.utils import get_app_logger

logger = get_app_logger("selling_price_repository")

class SellingPriceRepository:
    """Repository for selling price mapping database operations"""

    @staticmethod
    def get_price_field_by_user_type(user_type: str) -> Optional[str]:
        """
        Fetch the price field name for a given user_type from sellingpricemapping table.
        Args:
            user_type: Type of user (e.g., 'customer', 'distributor', 'peer', 'employee')

        Returns:
            The selling_price_key (field name) to use for this user type, or None if not found
        """
        try:
            query = """
                SELECT selling_price_key 
                FROM sellingpricemapping 
                WHERE user_type = :user_type AND status = true
                LIMIT 1
            """

            result = execute_raw_sql_readonly(query, {"user_type": user_type})
            if result and len(result) > 0:
                price_key = result[0].get("selling_price_key")
                logger.info(f"selling_price_key_found | user_type={user_type} price_key={price_key}")
                return price_key
            else:
                logger.warning(f"selling_price_key_not_found | user_type={user_type}")
                return None

        except Exception as e:
            logger.error(f"selling_price_repository_error | user_type={user_type} error={str(e)}", exc_info=True)
            return None

