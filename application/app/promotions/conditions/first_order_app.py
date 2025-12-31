from app.core.constants import PromotionErrorCode
from app.repository.promotions import PromotionsRepository
from app.logging.utils import get_app_logger
logger = get_app_logger("app.promotions.conditions.first_order_app")


async def validate(user_id: str) -> dict:
    repo = PromotionsRepository()
    user_orders_count = await repo.get_user_orders_count_by_channel(user_id, "app")
    
    if user_orders_count >= 1:
        logger.warning(f"User has previous app orders: {user_orders_count}")
        return {
            "valid": False,
            "error": {
                "code": PromotionErrorCode.NOT_FIRST_PURCHASE,
                "field": "user_frequency",
                "message": "Promotion only for users with no previous app orders",
                "details": {"user_orders_count": user_orders_count, "channel": "app"}
            }
        }
    return {"valid": True}
