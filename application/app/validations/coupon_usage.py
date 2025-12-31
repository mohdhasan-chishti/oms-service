from typing import Dict, Optional
from app.core.constants import PromotionErrorCode
from app.repository.promotions import PromotionsRepository
from app.logging.utils import get_app_logger
logger = get_app_logger("app.validations.coupon_usage")


class CouponUsageValidator:
    def __init__(self, repository: Optional[PromotionsRepository] = None):
        self.repository = repository or PromotionsRepository()

    async def validate(self, promotion_doc: Dict, user_id: str) -> Dict:
        coupon_code = promotion_doc.get("coupon_code")
        if not coupon_code:
            logger.error(f"Coupon code missing in promotion doc | promotion_code={promotion_doc.get('promotion_code')}")
            return {
                "valid": False,
                "error": {
                    "code": PromotionErrorCode.INVALID_PROMOTION,
                    "field": "coupon_code",
                    "message": "Coupon code is missing",
                    "details": {}
                }
            }

        max_usage = promotion_doc.get("max_usage_of_coupon")
        max_per_user = promotion_doc.get("max_uses_per_user")

        if max_usage:
            total_usage = await self.repository.get_coupon_total_usage(coupon_code)
            if total_usage >= max_usage:
                logger.warning(f"Coupon total usage limit reached | code={coupon_code} total={total_usage} max={max_usage}")
                return {
                    "valid": False,
                    "error": {
                        "code": PromotionErrorCode.COUPON_USAGE_LIMIT_REACHED,
                        "field": "max_usage_of_coupon",
                        "message": f"Coupon has reached maximum usage limit ({max_usage} times)",
                        "details": {"current_usage": total_usage, "max_usage": max_usage}
                    }
                }

        if max_per_user:
            user_usage = await self.repository.get_coupon_user_usage(coupon_code, user_id)
            if user_usage >= max_per_user:
                logger.warning(f"Coupon user usage limit reached | code={coupon_code} user={user_id} usage={user_usage} max={max_per_user}")
                return {
                    "valid": False,
                    "error": {
                        "code": PromotionErrorCode.COUPON_USER_LIMIT_REACHED,
                        "field": "max_uses_per_user",
                        "message": f"You have already used this coupon {user_usage} time(s). Maximum allowed: {max_per_user}",
                        "details": {"current_usage": user_usage, "max_per_user": max_per_user}
                    }
                }

        return {"valid": True}
