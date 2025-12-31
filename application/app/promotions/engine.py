from typing import Dict, List, Optional
from decimal import Decimal
from fastapi import HTTPException

# Repository
from app.repository.promotions import PromotionsRepository

# Validations
from app.validations.promotions import PromotionValidator
from app.validations.coupon_usage import CouponUsageValidator

# Constants
from app.core.constants import PromotionOfferType, PromotionErrorCode, PromotionUserFrequency

# Events
from app.promotions.events import flat_discount, cashback, freebee

# Conditions
from app.promotions.conditions import first_order_ever, first_order_app, first_order_pos

USER_FREQUENCY_VALIDATORS = {
    PromotionUserFrequency.FIRST_ORDER_EVER: first_order_ever.validate,
    PromotionUserFrequency.FIRST_ORDER_APP: first_order_app.validate,
    PromotionUserFrequency.FIRST_ORDER_POS: first_order_pos.validate,
}

# Strategies
from app.promotions.strategy.flat_discount import FlatDiscountStrategy

# Logging
from app.logging.utils import get_app_logger
logger = get_app_logger("app.promotions_engine")


class PromotionEngine:
    """A promotion engine for validating and computing promotions."""

    def __init__(self, repository: Optional[PromotionsRepository] = None, suppress_error_logs: bool = False):
        """Initialize the promotion engine with optional dependency injection.
        Args:
            repository: Optional PromotionsRepository instance for dependency injection
            suppress_error_logs: If True, suppresses error logging (useful for availability checks)
        """
        self.repository = repository or PromotionsRepository()
        self.suppress_error_logs = suppress_error_logs

    async def validate_and_compute(self, promotion_code: str, order_data: Dict, user_id: str, channel: str, payment_modes: List[str], facility_code: Optional[str] = None, promotion_doc: Optional[Dict] = None, promotion_type: Optional[str] = None, usage: str = "calculate") -> Optional[Dict]:
        """Main method to validate and compute promotion benefits.
        Args:
            promotion_code: The promotion code to validate
            order_data: Order information dictionary
            user_id: User identifier
            channel: Sales channel
            payment_modes: List of accepted payment modes
            facility_code: Optional facility code for facility-specific promotions
            promotion_doc: Optional promotion document (if already retrieved, avoids extra fetch)
            
        Returns:
            Dictionary containing promotion computation results or None
        Raises:
            HTTPException: For validation errors or system failures
        """
        try:
            # Step 1: Retrieve promotion (skip if already provided)
            if promotion_doc is None:
                facility_name = order_data.get("facility_name")
                if not facility_name:
                    raise HTTPException(
                        status_code=400,
                        detail={"error_code": "MISSING_FACILITY", "message": "facility_name is required for promotion lookup"}
                    )
                promotion_doc = await self.get_promotion(promotion_code, facility_name, promotion_type)

            # Step 2: Basic validation
            await self.validate_promotion_basic(promotion_doc, order_data, channel, payment_modes, usage)

            # Step 3: Coupon usage validation (if applicable)
            if promotion_doc.get("offer_type") == PromotionOfferType.COUPON:
                await self.validate_coupon_usage(promotion_doc, user_id)

            # Step 4: User frequency validation
            await self.validate_user_frequency(promotion_doc, user_id)

            # Step 4: Compute discount
            order_amount = Decimal(str(order_data.get("total_amount", 0)))
            discount_amount = await self.compute_discount(promotion_doc, order_amount)

            # Step 5: Build response
            final_response = await self.build_response(promotion_code, promotion_doc, order_amount, discount_amount)
            return final_response

        except HTTPException:
            if not self.suppress_error_logs:
                logger.error(f"validate_and_compute_http_exception | code={promotion_code} user={user_id}", exc_info=True)
            else:
                logger.debug(f"validate_and_compute_http_exception | code={promotion_code} user={user_id}", exc_info=True)
            raise
        except Exception as e:
            if not self.suppress_error_logs:
                logger.error(f"validate_and_compute_error | code={promotion_code} user={user_id} error={e}", exc_info=True)
            else:
                logger.debug(f"validate_and_compute_error | code={promotion_code} user={user_id} error={e}", exc_info=True)
            raise HTTPException(status_code=500, 
                detail={"error_code": "INTERNAL_ERROR", "message": "Failed to process promotion"}
            )


    async def get_promotion(self, promotion_code: str, facility_name: str, promotion_type: Optional[str] = None) -> Dict:
        promotion_doc = await self.repository.get_promotion_smart(promotion_code, facility_name, promotion_type)
        
        logger.info(f"Promotion doc retrieved: {promotion_doc}")

        if not promotion_doc:
            if not self.suppress_error_logs:
                logger.error(f"Promotion not found or inactive: {promotion_code}")
            else:
                logger.debug(f"Promotion not found or inactive: {promotion_code}")
            raise HTTPException(
                status_code=404, 
                detail={
                    "error_code": PromotionErrorCode.PROMO_NOT_FOUND, 
                    "message": f"Promotion code '{promotion_code}' not found or inactive"
                }
            )

        return promotion_doc

    async def validate_promotion_basic(self, promotion_doc: Dict, order_data: Dict, channel: str, payment_modes: List[str], usage: str = "calculate") -> None:
        """Perform basic promotion validation.

        Args:
            promotion_doc: Promotion document
            order_data: Order information
            channel: Sales channel (app, pos)
            payment_modes: List of payment modes
            usage: Usage context ('calculate' or 'order_creation')

        Raises:
            HTTPException: If basic validation fails
        """
        validator = PromotionValidator(promotion_doc, order_data, self.suppress_error_logs, usage)
        errors = validator.validate_all(channel, payment_modes)

        if errors:
            if not self.suppress_error_logs:
                logger.error(f"Promotion validation failed: {errors}")
            else:
                logger.debug(f"Promotion validation failed: {errors}")
            raise HTTPException(
                status_code=400, 
                detail={
                    "error_code": PromotionErrorCode.INVALID_PROMOTION, 
                    "message": "Promotion validation failed", 
                    "errors": errors
                }
            )

    async def validate_coupon_usage(self, promotion_doc: Dict, user_id: str) -> None:
        validator = CouponUsageValidator(self.repository)
        result = await validator.validate(promotion_doc, user_id)
        
        if not result.get("valid"):
            if not self.suppress_error_logs:
                logger.error(f"Coupon usage validation failed: {result}")
            else:
                logger.debug(f"Coupon usage validation failed: {result}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": result.get("error", {}).get("code", PromotionErrorCode.INVALID_PROMOTION),
                    "message": result.get("error", {}).get("message", "Coupon usage validation failed"),
                    "errors": [result.get("error")]
                }
            )

    async def validate_user_frequency(self, promotion_doc: Dict, user_id: str) -> None:
        """Validate user frequency constraints.

        Args:
            promotion_doc: Promotion document
            user_id: User identifier

        Raises:
            HTTPException: If user frequency validation fails
        """
        user_frequency_value = promotion_doc.get("user_frequency", [])
        if not user_frequency_value:
            return

        user_freq = user_frequency_value[0] if isinstance(user_frequency_value, list) else user_frequency_value

        validator = USER_FREQUENCY_VALIDATORS.get(user_freq)
        if not validator:
            if not self.suppress_error_logs:
                logger.error(f"Unsupported user_frequency: {user_freq}")
            else:
                logger.debug(f"Unsupported user_frequency: {user_freq}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": PromotionErrorCode.INVALID_PROMOTION, 
                    "message": f"Unsupported user_frequency: {user_freq}"
                }
            )

        result = await validator(user_id)
        if not result.get("valid"):
            if not self.suppress_error_logs:
                logger.error(f"User frequency validation failed: {result}")
            else:
                logger.debug(f"User frequency validation failed: {result}")
            raise HTTPException(
                status_code=400, 
                detail={
                    "error_code": PromotionErrorCode.INVALID_PROMOTION, 
                    "message": "Promotion validation failed", 
                    "errors": [result.get("error")]
                }
            )

    async def compute_discount(self, promotion_doc: Dict, order_amount: Decimal) -> Decimal:
        """Compute discount amount based on promotion type.

        Args:
            promotion_doc: Promotion document
            order_amount: Order total amount
            
        Returns:
            Calculated discount amount
        """
        offer_type = promotion_doc.get("offer_type")
        if offer_type == PromotionOfferType.FLAT_DISCOUNT:
            discount_amount = flat_discount.compute(promotion_doc, order_amount)
        elif offer_type == PromotionOfferType.CASHBACK:
            discount_amount = cashback.compute(promotion_doc, order_amount)
        elif offer_type == PromotionOfferType.FREEBEE:
            discount_amount = freebee.compute(promotion_doc, order_amount)
        elif offer_type == PromotionOfferType.COUPON:
            discount_amount = flat_discount.compute(promotion_doc, order_amount)
        else:
            discount_amount = Decimal("0")

        logger.info(f"Promotion offer_type: {offer_type} discount_amount: {discount_amount}")
        return discount_amount

    async def build_response(self, promotion_code: str, promotion_doc: Dict, order_amount: Decimal, discount_amount: Decimal) -> Dict:
        """Build the final response dictionary.

        Args:
            promotion_code: The promotion code
            promotion_doc: Promotion document
            order_amount: Original order amount
            discount_amount: Calculated discount amount

        Returns:
            Response dictionary with promotion details
        """
        offer_type = promotion_doc.get("offer_type")

        cashback_amount = Decimal("0")
        response = {
            "promotion_code": promotion_code,
            "promotion_type": offer_type,
            "promotion_discount": discount_amount,
        }

        # Add freebees for freebee promotions
        if offer_type == PromotionOfferType.FREEBEE:
            freebees_list = freebee.get_freebees(promotion_doc)
            response["freebees"] = freebees_list
        elif offer_type == PromotionOfferType.CASHBACK:
            cashback_amount = discount_amount
            response["promotion_discount"] = cashback_amount
        elif offer_type in [PromotionOfferType.FLAT_DISCOUNT, PromotionOfferType.COUPON]:
            cashback_amount = discount_amount
            response["promotion_discount"] = cashback_amount
            response["discount_percentage"] = promotion_doc.get("discount_percentage", 0)
            response["max_discount"] = promotion_doc.get("max_discount", 0)
            response["offer_sub_type"] = promotion_doc.get("offer_sub_type", "flat")

        return response

