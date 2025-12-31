from decimal import Decimal
from typing import Dict
from app.logging.utils import get_app_logger

logger = get_app_logger("app.promotions.events.cashback")

def compute(promotion_doc: Dict, order_amount: Decimal) -> Decimal:
    logger.info(f"cashback_compute | promotion_doc={promotion_doc} order_amount={order_amount}")
    # TODO: Implement cashback computation logic
    return Decimal(str(promotion_doc.get("discount_amount", 0)))
