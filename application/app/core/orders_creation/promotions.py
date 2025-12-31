"""
Order promotion functions
"""
from decimal import Decimal
from typing import Dict, List

from fastapi import HTTPException

from app.promotions.engine import PromotionEngine
from app.validations.order_promotion_validation import OrderPromotionValidator
from app.logging.utils import get_app_logger

logger = get_app_logger("app.core.orders_creation.promotions")


async def validate_and_apply_promotion(
    promotion_code: str,
    customer_id: str,
    enriched_facility_data: Dict,
    origin: str,
    payment_modes: List[str],
    promotion_type: str,
    cart_total: Decimal
) -> Dict:
    """
    Validate and compute promotion for an order
    
    Returns: promotion_result dict with discount details
    """
    promotion_result = {}
    
    # Skip if no promotion code or guest customer
    if not promotion_code or customer_id == 'guest':
        return promotion_result
    
    # Get facility from enriched_facility_data (already filtered in order_functions.py)
    facility_name = list(enriched_facility_data.keys())[0]
    facility_data = enriched_facility_data[facility_name]
    facility_total = facility_data['total']
    facility_items = facility_data['items']
    
    # Prepare order data for promotion validation
    order_data_for_promo = {"facility_name": facility_name, "total_amount": facility_total}
    
    # Validate and compute promotion
    promotion_engine = PromotionEngine()
    promotion_result = await promotion_engine.validate_and_compute(
        promotion_code,
        order_data_for_promo,
        customer_id,
        origin,
        payment_modes,
        promotion_type=promotion_type,
        usage="order_creation"
    )
    
    logger.info(f"promotion_validated | code={promotion_code} type={promotion_type} discount={promotion_result.get('promotion_discount')}")
    
    # Additional validation: Compare promotion discount with cart calculation
    promotion_validator = OrderPromotionValidator()
    computed_promotion_type = promotion_result.get("promotion_type", "")
    await promotion_validator.validate_promotion_discount(
        facility_items,
        promotion_code,
        promotion_result,
        computed_promotion_type,
        facility_name=facility_name
    )
    
    logger.info(f"promotion_discount_validation_passed | code={promotion_code}")
    
    return promotion_result

