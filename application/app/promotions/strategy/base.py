from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional


class BasePromotionStrategy(ABC):
    @abstractmethod
    def compute_discount(self, promotion_doc: Dict, order_amount: Decimal) -> Decimal:
        pass

    @abstractmethod
    def apply_to_items(self, items: List[Dict], discount_amount: Decimal) -> Optional[List[Dict]]:
        pass