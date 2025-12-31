from decimal import Decimal
from typing import Dict

from app.promotions.strategy.flat_discount import FlatDiscountStrategy


def compute(promotion_doc: Dict, order_amount: Decimal) -> Decimal:
    strategy = FlatDiscountStrategy()
    return strategy.compute_discount(promotion_doc, order_amount)
