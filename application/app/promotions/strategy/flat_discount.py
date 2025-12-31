from decimal import Decimal
from typing import Dict, List, Optional
from .base import BasePromotionStrategy


class FlatDiscountStrategy(BasePromotionStrategy):
    def compute_discount(self, promotion_doc: Dict, order_amount: Decimal) -> Decimal:
        if promotion_doc.get("offer_sub_type") == "percentage":
            discount_percentage = Decimal(str(promotion_doc.get("discount_percentage", 0)))
            max_discount_amount = Decimal(str(promotion_doc.get("max_discount", 0)))

            percentage_discount = (order_amount * discount_percentage) / 100
            percentage_discount = min(percentage_discount, max_discount_amount)
            return percentage_discount.quantize(Decimal('0.01'))
        else:
            return Decimal(str(promotion_doc.get("discount_amount", 0)))

    def apply_to_items(self, items: List[Dict], discount_amount: Decimal) -> Optional[List[Dict]]:
        if not items or discount_amount == 0:
            return None

        items_subtotal = sum(Decimal(str(item.get("sale_price", 0))) * Decimal(str(item.get("quantity", 0))) for item in items)
        if items_subtotal == 0:
            return None

        remaining_discount = discount_amount
        discounted_items = []

        for idx, item in enumerate(items):
            item_price = Decimal(str(item.get("sale_price", 0)))
            item_qty = Decimal(str(item.get("quantity", 0)))
            item_total = item_price * item_qty

            if idx == len(items) - 1:
                item_discount = remaining_discount
            else:
                item_discount = (item_total / items_subtotal) * discount_amount
                item_discount = item_discount.quantize(Decimal("0.01"))

            item_discount_per_unit = (item_discount / item_qty).quantize(Decimal("0.01"))
            new_sale_price = item_price - item_discount_per_unit

            discounted_item = item.copy()
            discounted_item["sale_price"] = float(new_sale_price)
            discounted_items.append(discounted_item)

            remaining_discount -= item_discount_per_unit * item_qty

        return discounted_items