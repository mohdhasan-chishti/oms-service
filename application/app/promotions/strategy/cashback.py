from decimal import Decimal
from typing import Dict, List, Optional
from app.promotions.strategy.base import BasePromotionStrategy


class CashbackStrategy(BasePromotionStrategy):
    def compute_discount(self, promotion_doc: Dict, order_amount: Decimal) -> Decimal:
        return Decimal(str(promotion_doc.get("discount_amount", 0)))

    def apply_to_items(self, items: List[Dict], discount_amount: Decimal) -> Optional[List[Dict]]:
        """
        For cashback offers, return items with original sale prices unchanged
        since cashback is given after successful delivery, not as immediate discount
        """
        if not items:
            return None
            
        # Return items with original sale prices (no price modification for cashback)
        cashback_items = []
        for item in items:
            cashback_item = item.copy()
            # Keep original sale price for cashback offers
            cashback_items.append(cashback_item)
            
        return cashback_items