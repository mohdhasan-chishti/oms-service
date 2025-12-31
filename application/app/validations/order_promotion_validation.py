from decimal import Decimal
from typing import List, Dict, Optional
from fastapi import HTTPException

from app.promotions.strategy.flat_discount import FlatDiscountStrategy
from app.promotions.category_filter import CategoryFilter
from app.cart.repository import CartRepository
from app.dto.cart import CartItem
from app.logging.utils import get_app_logger

logger = get_app_logger("app.validations.order_promotion_validation")


class OrderPromotionValidator:
    """Simple validator to ensure promotion discount calculations are consistent."""

    def __init__(self):
        self.flat_discount_strategy = FlatDiscountStrategy()
        self.repository = CartRepository()

    async def validate_promotion_discount(self, order_items: List[Dict], promotion_code: str, promotion_result: Dict, promotion_type: str, facility_name: Optional[str] = None) -> bool:
        """
        Enhanced validation: Check if promotion discount matches expected calculation with category-based filtering.

        Args:
            order_items: List of order items with sku, quantity, sale_price, and category fields
            promotion_code: The promotion code being applied
            promotion_result: Result from promotion engine validation
            promotion_type: Type of promotion (flat_discount, cashback, etc.)
            facility_name: Optional facility name for category-based promotion validation
        """
        try:
            promotion_discount = Decimal(str(promotion_result.get("promotion_discount", 0)))

            # Step 1: If facility_name is provided, perform category-based validation first
            eligible_items_for_discount = order_items  # Default to all items

            if facility_name:
                try:
                    promotion_doc = await self.repository.get_promotion_by_code(promotion_code, facility_name, promotion_type)

                    if promotion_doc:
                        # Check if promotion has category or SKU filters
                        has_category_filters = (
                            promotion_doc.get("applicable_categories") or
                            promotion_doc.get("excluded_categories") or
                            promotion_doc.get("applicable_skus") or
                            promotion_doc.get("excluded_skus")
                        )

                        if has_category_filters:
                            logger.info(f"Category-based promotion detected | code={promotion_code}")

                            # Convert order items to CartItem objects for filtering
                            cart_items = []
                            for item in order_items:
                                cart_item = CartItem(
                                    sku=item["sku"],
                                    mrp=Decimal(str(item.get("mrp", 0))),
                                    sale_price=Decimal(str(item.get("original_sale_price", item.get("sale_price", 0)))),
                                    quantity=item["quantity"],
                                    category=item.get("category"),
                                    sub_category=item.get("sub_category"),
                                    sub_sub_category=item.get("sub_sub_category")
                                )
                                cart_items.append(cart_item)

                            # Get eligible items using category filter
                            eligible_cart_items = CategoryFilter.get_eligible_items(cart_items, promotion_doc)
                            eligible_skus = {item.sku for item in eligible_cart_items}

                            # Filter order items to only eligible ones for discount calculation
                            eligible_items_for_discount = [item for item in order_items if item["sku"] in eligible_skus]

                            # Validate that non-eligible items don't have discounts
                            for item in order_items:
                                sku = item["sku"]
                                actual_sale_price = Decimal(str(item.get("sale_price", 0)))
                                original_sale_price = Decimal(str(item.get("original_sale_price", actual_sale_price)))

                                if sku not in eligible_skus:
                                    # Non-eligible item should not have discount
                                    if actual_sale_price != original_sale_price:
                                        logger.error(f"Non-eligible item has discount | sku={sku} original={original_sale_price} actual={actual_sale_price}")
                                        raise HTTPException(
                                            status_code=400,
                                            detail=f"Non-eligible item {sku} should not have discount applied"
                                        )

                            logger.info(f"Category filtering applied | total_items={len(order_items)} eligible_items={len(eligible_items_for_discount)}")

                except Exception as e:
                    logger.warning(f"Category validation failed, falling back to original logic | error={e}")
                    # Fall back to original validation logic if category validation fails
                    eligible_items_for_discount = order_items

            # Step 2: Perform discount calculation validation on eligible items
            if promotion_type.lower() == "flat_discount" or promotion_type.lower() == "coupon":
                # Create items with original_sale_price for strategy calculation
                original_items = []
                eligible_total_cart_amount = Decimal("0")
                for item in eligible_items_for_discount:
                    original_item = item.copy()
                    # Use original_sale_price as the base for discount calculation
                    original_item["sale_price"] = item.get("original_sale_price", item.get("sale_price"))
                    original_items.append(original_item)
                    eligible_total_cart_amount += Decimal(str(item.get("original_sale_price", item.get("sale_price")))) * Decimal(str(item["quantity"]))

                # percenateg flat discount
                if promotion_result.get("offer_sub_type") == "percentage":
                    promotion_discount = self.flat_discount_strategy.compute_discount(promotion_result, eligible_total_cart_amount)
                    promotion_result["promotion_discount"] = promotion_discount

                expected_items = self.flat_discount_strategy.apply_to_items(original_items, promotion_discount)
                if not expected_items:
                    raise HTTPException(status_code=400, detail="Invalid discount calculation")

                # Validate that the eligible order items have the correct discounted prices
                for orig, expected in zip(eligible_items_for_discount, expected_items):
                    expected_sale_price = Decimal(str(expected.get("sale_price", 0)))
                    actual_sale_price = Decimal(str(orig.get("sale_price", 0)))
                    
                    # Allow small rounding differences (up to 0.01 per item)
                    if abs(actual_sale_price - expected_sale_price) > Decimal("0.01"):
                        sku = orig.get("sku", "unknown")
                        logger.error(f"Item price mismatch | sku={sku} expected={expected_sale_price} actual={actual_sale_price}")
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Item price mismatch for SKU {sku}: expected {expected_sale_price}, got {actual_sale_price}"
                        )

                logger.info(f"Flat discount item prices validation passed | code={promotion_code} eligible_items={len(eligible_items_for_discount)}")

            elif promotion_type.lower() == "freebee":
                # Get freebees from promotion result (already fetched by promotion engine)
                freebees_list = promotion_result.get("freebees", [])
                if not freebees_list:
                    raise HTTPException(status_code=400, detail=f"No freebees found for promotion {promotion_code}")

                freebee_prices = {}
                for f in freebees_list:
                    freebee_prices[f["child_sku"]] = float(f["selling_price"])

                # Validate freebee items have correct prices
                for item in order_items:
                    sku = item.get("sku")
                    is_freebee = item.get("is_freebee", False)
                    sale_price = float(item.get("sale_price", 0))

                    if is_freebee:
                        if sku not in freebee_prices:
                            raise HTTPException(
                                status_code=400,
                                detail=f"SKU {sku} is marked as freebee but not found in promotion {promotion_code}"
                            )

                        expected_price = freebee_prices[sku]
                        if abs(sale_price - expected_price) >= 0.01:
                            logger.error(f"Freebee price mismatch | sku={sku} expected={expected_price} actual={sale_price}")
                            raise HTTPException(
                                status_code=400,
                                detail=f"Freebee price mismatch for SKU {sku}: expected ₹{expected_price}, got ₹{sale_price}"
                            )

                logger.info(f"Freebee validation passed | code={promotion_code} freebee_items={len([i for i in order_items if i.get('is_freebee')])}")

            logger.info(f"Promotion validation passed | code={promotion_code} discount={promotion_discount}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Promotion validation error | code={promotion_code} error={e}")
            raise HTTPException(status_code=500, detail="Promotion validation failed")
