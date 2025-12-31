from decimal import Decimal
from typing import Dict, List, Optional
from .base import BasePromotionStrategy


class FreebeeStrategy(BasePromotionStrategy):
    """Strategy for freebee promotions - provides free items with minimal cart discount"""
    
    def compute_discount(self, promotion_doc: Dict, order_amount: Decimal) -> Decimal:
        """
        Compute discount for freebee promotions.
        Returns the minimal discount amount (usually ₹1) as specified in promotion doc.
        """
        return Decimal(str(promotion_doc.get("discount_amount", 0)))

    def apply_to_items(self, items: List[Dict], discount_amount: Decimal) -> Optional[List[Dict]]:
        """
        For freebee promotions, we don't apply discounts to cart items.
        The main benefit is the free items, not discounts on existing items.
        Returns None to indicate no item-level processing.
        """
        return None
