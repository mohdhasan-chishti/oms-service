import time
from typing import Dict, List, Optional
from decimal import Decimal

# Services
from app.services.typesense_service import TypesenseService

# Logging
from app.logging.utils import get_app_logger
logger = get_app_logger("app.cart_repository")


class CartRepository:
    """Repository for cart-related data operations"""

    def __init__(self):
        self.typesense_service = TypesenseService()

    async def get_available_promotions(self, total_amount: Decimal, user_id: Optional[str] = None, channel: str = "app", facility_name = None) -> List[Dict]:
        """
        Get list of available promotions based on cart total and user context
        
        Args:
            total_amount: Total cart amount
            user_id: Optional user ID for personalized promotions
            channel: Sales channel (app, pos)
            
        Returns:
            List of promotion documents
        """
        try:
            now_ts = int(time.time())
            params = {
                "q": "*",
                "filter_by": f"facility_code:={facility_name} && discount_at:={channel} && is_active:=true && start_date:<={now_ts} && end_date:>= {now_ts} && min_purchase:<= {total_amount} && offer_type:!=[coupon]",
                "sort_by": "priority:desc",
                "page": 1,
                "per_page": 20
            }
            result = await self.typesense_service.search_documents(params, "promotions")
            hits = result.get("hits", [])
            promotions = [hit["document"] for hit in hits]
            logger.info(f"get_available_promotions | total_amount={total_amount} user_id={user_id} channel={channel} facility_code={facility_name} count={len(promotions)}")
            return promotions

        except Exception as e:
            logger.error(f"get_available_promotions_error | total_amount={total_amount} user_id={user_id} facility_code={facility_name} error={e}", exc_info=True)
            raise

    async def get_promotion_by_code(self, promotion_code: str, facility_name: str, promotion_type: Optional[str] = None) -> Optional[Dict]:
        try:
            now_ts = int(time.time())
            
            if promotion_type == "coupon":
                filter_by = f"coupon_code:=`{promotion_code}` && offer_type:=coupon && facility_code:=`{facility_name}` && is_active:=true && start_date:<={now_ts} && end_date:>={now_ts}"
            else:
                filter_by = f"promotion_code:=`{promotion_code}` && facility_code:=`{facility_name}` && is_active:=true && start_date:<={now_ts} && end_date:>={now_ts}"
            
            params = {
                "q": "*",
                "query_by": "name,description",
                "filter_by": filter_by,
                "per_page": 1
            }

            result = await self.typesense_service.search_documents(params, "promotions")
            hits = result.get("hits", [])

            promotion = hits[0]["document"] if hits else None

            logger.info(f"get_promotion_by_code | code={promotion_code} type={promotion_type} found={promotion is not None}")

            return promotion

        except Exception as e:
            logger.error(f"get_promotion_by_code_error | code={promotion_code} error={e}", exc_info=True)
            raise

    async def validate_promotion_applicability(self, promotion: Dict, total_amount: Decimal, channel: str, payment_modes: List[str]) -> Dict:
        """
        Validate if a promotion is applicable for given conditions
        
        Args:
            promotion: Promotion document
            total_amount: Cart total amount
            channel: Sales channel
            payment_modes: Available payment modes
            
        Returns:
            Dictionary with validation result and details
        """
        try:
            errors = []

            # Check minimum order amount
            min_purchase = Decimal(str(promotion.get("min_purchase", 0)))
            if min_purchase > 0 and total_amount < min_purchase:
                errors.append(f"Minimum purchase amount of ₹{min_purchase} required")

            # Check channel compatibility
            promotion_channels = promotion.get("channels", [])
            if promotion_channels and channel not in promotion_channels:
                errors.append(f"Promotion not available for {channel} channel")

            # Check payment mode compatibility
            promotion_payment_modes = promotion.get("payment_modes", [])
            if promotion_payment_modes:
                compatible_modes = set(payment_modes) & set(promotion_payment_modes)
                if not compatible_modes:
                    errors.append("No compatible payment modes available")

            is_valid = len(errors) == 0
            result = {
                "is_valid": is_valid,
                "errors": errors,
                "promotion_code": promotion.get("promotion_code"),
                "title": promotion.get("name", ""),
                "description": promotion.get("description", "")
            }

            logger.info(f"validate_promotion_applicability | code={promotion.get('promotion_code')} valid={is_valid} errors={errors}")
            return result

        except Exception as e:
            logger.error(f"validate_promotion_applicability_error | code={promotion.get('promotion_code', 'unknown')} error={e}", exc_info=True)
            raise
