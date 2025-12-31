"""
Selling Price Service
Handles user-type-based price mapping and validation
"""

from typing import Dict, Optional, List
from app.repository.selling_price_repository import SellingPriceRepository
from app.logging.utils import get_app_logger

logger = get_app_logger("selling_price_service")

class SellingPriceService:
    """Service for managing user-type-based selling prices"""

    # Default mapping if database lookup fails
    DEFAULT_PRICE_FIELD_MAPPING = {
        "customer": "selling_price",
        "distributor": "distributor_selling_price",
        "peer": "peer_selling_price",
        "employee": "employee_selling_price"
    }

    @staticmethod
    def get_price_field_for_user_type(user_type: str) -> str:
        """
        Get the price field name for a user type.
        First tries database lookup via repository, then falls back to default mapping.
        Args:
            user_type: Type of user

        Returns:
            The field name to use for price validation
        """
        # Try database lookup first via repository
        db_price_field = SellingPriceRepository.get_price_field_by_user_type(user_type)
        if db_price_field:
            return db_price_field

        # Fall back to default mapping
        price_field = SellingPriceService.DEFAULT_PRICE_FIELD_MAPPING.get(user_type.lower(), "selling_price")
        logger.info(f"using_default_price_field | user_type={user_type} price_field={price_field}")
        return price_field

    @staticmethod
    def validate_user_type(user_type: str) -> bool:
        """
        Validate if user_type is valid (exists in DB or in default mapping).
        Args:
            user_type: Type of user to validate

        Returns:
            True if valid

        Raises:
            ValueError: If user_type is invalid
        """
        if not user_type or not user_type.strip():
            logger.error("user_type cannot be empty")
            raise ValueError("user_type cannot be empty")

        user_type = user_type.strip()
        # Check if user_type exists in sellingpricemapping table
        price_key = SellingPriceRepository.get_price_field_by_user_type(user_type)

        # If not in DB, check default mapping
        if not price_key:
            default_key = SellingPriceService.DEFAULT_PRICE_FIELD_MAPPING.get(user_type.lower())
            if not default_key:
                logger.error(f"Invalid user_type: {user_type} | Not found in DB or default mapping")
                raise ValueError(f"Invalid user_type: {user_type}. Please use a valid user type from the system.")
            price_key = default_key

        logger.info(f"user_type_validation_passed | user_type={user_type} price_key={price_key}")
        return True


