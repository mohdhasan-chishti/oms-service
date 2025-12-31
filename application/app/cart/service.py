from typing import Dict, List, Optional
from decimal import Decimal
from fastapi import HTTPException

# Repository
from app.cart.repository import CartRepository

# Promotions Engine
from app.promotions.engine import PromotionEngine
from app.promotions.category_filter import CategoryFilter

# Promotion Strategies
from app.promotions.strategy.flat_discount import FlatDiscountStrategy
from app.promotions.strategy.cashback import CashbackStrategy
from app.promotions.strategy.freebee import FreebeeStrategy

# Constants
from app.core.constants import PromotionOfferType

# DTOs
from app.dto.cart import (
    PromotionListRequest, PromotionListResponse,
    CartDiscountRequest, CartDiscountResponse, CartItemResponse, FreebeeItem
)

# Freebee events
from app.promotions.events import freebee

# Stock validation
from app.validations.stock import StockValidator

# Logging
from app.logging.utils import get_app_logger
logger = get_app_logger("app.cart_service")


class CartService:
    """Service for cart operations including promotions and discount calculations"""

    def __init__(self):
        self.repository = CartRepository()
        self.promotion_engine = PromotionEngine()  # Default: normal error logging

    @staticmethod
    def map_offer_sub_type(offer_type, offer_sub_type: str = "") -> str:
        if offer_type == PromotionOfferType.COUPON:
            offer_sub_type_lower = offer_sub_type.lower()
            if offer_sub_type_lower in ["percentage", "flat"]:
                return "discount"
            elif offer_sub_type_lower == "cashback":
                return "cashback"
        return ""

    def process_freebee_items(self, freebees_data: List[Dict], channel: str, facility_name: str, context: str = "") -> List[FreebeeItem]:
        """
        Common function to process freebee items with channel-based stock validation
        Args:
            freebees_data: List of freebee items from promotion
            channel: Sales channel (app, pos)
            facility_name: Facility name for stock validation
            context: Context for logging (e.g., "available_promotions", "discount_calculation")
        Returns:
            List of FreebeeItem objects after applying channel-based validation
        """
        freebee_items = []
        if not freebees_data:
            return freebee_items

        # For POS channel, send all freebee items without stock validation
        if channel == "pos":
            freebee_items = [FreebeeItem(child_sku=freebee_item.get("child_sku"), selling_price=freebee_item.get("selling_price")) for freebee_item in freebees_data]
            logger.info(f"freebee_{context}_pos_channel | added all freebee items without stock check | count={len(freebee_items)}")
        else:
            # For APP channel, check stock availability for each freebee item
            for freebee_item in freebees_data:
                wh_sku = freebee_item.get("wh_sku")
                child_sku = freebee_item.get("child_sku")
                selling_price = freebee_item.get("selling_price")

                # Only process if wh_sku is available
                if wh_sku:
                    try:
                        stock_validator = StockValidator(warehouse=facility_name, sku=wh_sku)
                        stock_data = stock_validator.get_stock()
                        available_quantity = stock_data.get("available_quantity", 0)

                        # Only add to list if stock is available (quantity > 0)
                        if available_quantity > 0:
                            freebee_items.append(FreebeeItem(child_sku=child_sku, selling_price=selling_price))
                            logger.info(f"freebee_{context}_app_stock_available | facility={facility_name} wh_sku={wh_sku} child_sku={child_sku} available_qty={available_quantity}")
                        else:
                            logger.warning(f"freebee_{context}_app_stock_unavailable | facility={facility_name} wh_sku={wh_sku} child_sku={child_sku} available_qty={available_quantity}")
                    except Exception as e:
                        # If stock check fails, don't include the freebee item
                        logger.warning(f"freebee_{context}_app_stock_check_failed | facility={facility_name} wh_sku={wh_sku} child_sku={child_sku} error={str(e)}")
                else:
                    # If no wh_sku, don't add to freebee list for app channel
                    logger.warning(f"freebee_{context}_app_no_wh_sku | child_sku={child_sku} - skipped (no wh_sku provided)")

        return freebee_items

    async def get_available_promotions(self, total_amount: Decimal, user_id: Optional[str], user_type: str, channel: str, facility_name: Optional[str], payment_modes: List[str], items: List = None) -> List[PromotionListResponse]:
        """
        Get list of available promotions for given cart total and items
        
        Args:
            total_amount: Total cart amount
            user_id: Optional user ID for personalized promotions
            channel: Sales channel (app, pos)
            facility_name: Optional facility code for facility-specific promotions
            payment_modes: Available payment modes
            items: Optional list of cart items with category information
            
        Returns:
            List of available promotions with category-based filtering
        """

        try:
            logger.info(f"get_available_promotions | total_amount={total_amount} user_id={user_id} facility_code={facility_name}")

            # Check if user_type is distributor - disable promotions for distributors
            if user_type and user_type.lower() in ['distributor']:
                logger.info(f"get_available_promotions | promotions_disabled_for_distributor | user_type={user_type}")
                return []

            # Create promotion engine with suppressed logs for availability checks
            quiet_promotion_engine = PromotionEngine(suppress_error_logs=True)

            # Get promotions from Typesense
            promotions = await self.repository.get_available_promotions(total_amount=total_amount,
                user_id=user_id,
                channel=channel,
                facility_name=facility_name
            )

            promotion_responses = []
            for promotion in promotions:
                promotion_code = promotion.get("promotion_code", "")
                is_applicable = False
                eligible_cart_value = total_amount  # Default to total amount

                try:
                    # If items are provided, calculate eligible cart value based on category filtering
                    if items:
                        eligible_items = CategoryFilter.get_eligible_items(items, promotion)
                        eligible_cart_value = CategoryFilter.calculate_eligible_cart_value(eligible_items)
                        min_purchase = Decimal(str(promotion.get("min_purchase", 0)))

                        # Check if no items are eligible or eligible cart value is below minimum purchase
                        if not eligible_items:
                            logger.debug(f"promotion_not_applicable | code={promotion_code} reason=no_eligible_items")
                            is_applicable = False
                        elif eligible_cart_value < min_purchase:
                            logger.debug(f"promotion_not_applicable | code={promotion_code} reason=min_purchase_not_met eligible_value={eligible_cart_value} min_purchase={min_purchase}")
                            is_applicable = False
                        else:
                            # Use eligible cart value for validation
                            order_data = {
                                "facility_name": facility_name,
                                "total_amount": float(eligible_cart_value),
                                "items": [{"sku": item.sku, "sale_price": float(item.sale_price), "quantity": item.quantity} for item in eligible_items]
                            }

                            validation_result = await quiet_promotion_engine.validate_and_compute(
                                promotion_code=promotion_code,
                                order_data=order_data,
                                user_id=user_id,
                                channel=channel,
                                payment_modes=payment_modes,
                                promotion_doc=promotion
                            )

                            if promotion.get("offer_type") == PromotionOfferType.FREEBEE:
                                is_applicable = bool(validation_result)
                            else:
                                is_applicable = bool(validation_result and validation_result.get("promotion_discount", 0) > 0)
                            logger.info(f"promotion_validation | code={promotion_code} applicable={is_applicable} eligible_items={len(eligible_items)} eligible_value={eligible_cart_value} min_purchase={min_purchase} discount={validation_result.get('promotion_discount', 0) if validation_result else 0}")
                    else:
                        # Fallback to original logic if no items provided
                        order_data = {
                            "facility_name": facility_name,
                            "total_amount": float(total_amount)
                        }

                        validation_result = await quiet_promotion_engine.validate_and_compute(
                            promotion_code=promotion_code,
                            order_data=order_data,
                            user_id=user_id,
                            channel=channel,
                            payment_modes=payment_modes,
                            promotion_doc=promotion
                        )

                        if promotion.get("offer_type") == PromotionOfferType.FREEBEE:
                            is_applicable = bool(validation_result)
                        else:
                            is_applicable = bool(validation_result and validation_result.get("promotion_discount", 0) > 0)
                        logger.info(f"promotion_validation | code={promotion_code} applicable={is_applicable} discount={validation_result.get('promotion_discount', 0) if validation_result else 0}")
                        
                except Exception as e:
                    # If validation fails, promotion is not applicable
                    logger.debug(f"promotion_not_applicable | code={promotion_code} reason={str(e)}")
                    is_applicable = False

                freebees_list = []
                if promotion.get("offer_type", "").strip().lower() == PromotionOfferType.FREEBEE:
                    freebees_data = freebee.get_freebees(promotion)
                    freebees_list = self.process_freebee_items(freebees_data, channel, facility_name, "available_promotions")
                    if channel == "app" and not freebees_list:
                        is_applicable = False
                        logger.warning("promotion_not_applicable_no_freebee_stock | code=%s channel=%s" % (promotion_code, channel))


                final_discount_amount = await quiet_promotion_engine.compute_discount(promotion, total_amount)
                promotion_response = PromotionListResponse(
                    promotion_code=promotion_code,
                    title=promotion.get("name", ""),
                    description=promotion.get("description", ""),
                    offer_type=promotion.get("offer_type", ""),
                    discount_amount=final_discount_amount,
                    min_purchase=Decimal(str(promotion.get("min_purchase", 0))),
                    is_applicable=is_applicable,
                    freebees=freebees_list,
                    promotion_facility=facility_name
                )

                promotion_responses.append(promotion_response)

            # Sort by applicability first, then by priority
            promotion_responses.sort(key=lambda x: (not x.is_applicable, -float(x.discount_amount)))

            logger.info(f"get_available_promotions_result | count={len(promotion_responses)} applicable={sum(1 for p in promotion_responses if p.is_applicable)}")
            return promotion_responses

        except Exception as e:
            logger.error(f"get_available_promotions_error | error={e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={"error_code": "INTERNAL_ERROR", "message": "Failed to fetch available promotions"}
            )

    async def calculate_cart_discount(self, cart_value: Decimal, promo_code: str, items: List, user_id: str, user_type: str, channel: str, payment_modes: List[str], facility_name: str, promotion_type: Optional[str] = None) -> CartDiscountResponse:
        """
        Calculate proportional discount for cart items based on promotion

        Args:
            cart_value: Total cart value
            promo_code: Promotion code to apply
            items: List of cart items
            user_id: User ID
            channel: Sales channel
            payment_modes: Available payment modes
            facility_code: Facility code for facility-specific promotions

        Returns:
            CartDiscountResponse with calculated discounts per item
        """
        try:
            logger.info(f"calculate_cart_discount_start | cart_value={cart_value} promo_code={promo_code} items_count={len(items)} facility_name={facility_name} promotion_type={promotion_type}")
            
            # Check if user_type is distributor - disable promotions for distributors
            if user_type and user_type.lower() in ['distributor']:
                logger.info(f"calculate_cart_discount | promotions_disabled_for_distributor | user_type={user_type}")
                raise HTTPException(status_code=400, detail={"error_code": "PROMOTION_NOT_ALLOWED", "message": "Promotions are not allowed for distributor accounts"})

            promotion_doc = await self.repository.get_promotion_by_code(promo_code, facility_name, promotion_type)
            logger.info(f"calculate_cart_discount_promotion_fetched | found={promotion_doc is not None}")
            if not promotion_doc:
                raise HTTPException(
                    status_code=404,
                    detail={"error_code": "PROMOTION_NOT_FOUND", "message": "Promotion not found"}
                )
            
            # Filter items based on promotion criteria (SKU and category filters)
            eligible_items = CategoryFilter.get_eligible_items(items, promotion_doc)
            
            if not eligible_items:
                raise HTTPException(
                    status_code=400,
                    detail={"error_code": "NO_ELIGIBLE_ITEMS", "message": "No items in cart are eligible for this promotion"}
                )
            
            # Calculate eligible cart value
            eligible_cart_value = CategoryFilter.calculate_eligible_cart_value(eligible_items)
            
            logger.info(f"Category filtering | total_items={len(items)} eligible_items={len(eligible_items)} eligible_value={eligible_cart_value}")
            
            # Prepare order data for promotion engine using eligible items only
            order_items = []
            for item in eligible_items:
                order_item = {
                    "sku": item.sku,
                    "mrp": float(item.mrp),
                    "sale_price": float(item.sale_price),
                    "quantity": item.quantity
                }
                order_items.append(order_item)

            order_data = {
                "total_amount": float(eligible_cart_value),
                "items": order_items,
                "facility_name": facility_name
            }

            offer_type = promotion_doc.get("offer_type", "").strip().lower()
            promotion_engine = PromotionEngine(suppress_error_logs=True) if offer_type == PromotionOfferType.COUPON else self.promotion_engine
            
            # Validate and compute promotion using existing engine
            logger.info(f"calculate_cart_discount_calling_engine | promo_code={promo_code} user_id={user_id}")
            promotion_result = await promotion_engine.validate_and_compute(
                promotion_code=promo_code,
                order_data=order_data,
                user_id=user_id,
                channel=channel,
                payment_modes=payment_modes,
                facility_code=facility_name,
                promotion_doc=promotion_doc,
                promotion_type=promotion_type,
                usage="calculate"
            )
            logger.info(f"calculate_cart_discount_engine_complete | result={promotion_result is not None}")

            if not promotion_result:
                raise HTTPException(
                    status_code=400,
                    detail={"error_code": "INVALID_PROMOTION", "message": "Promotion is not applicable"}
                )

            offer_type = promotion_doc.get("offer_type", "").strip().lower()
            logger.info(f"calculate_cart_discount_offer_type | promo_code={promo_code} offer_type='{offer_type}'")
            
            if offer_type in [PromotionOfferType.FLAT_DISCOUNT, PromotionOfferType.COUPON]:
                strategy = FlatDiscountStrategy()
            elif offer_type == PromotionOfferType.CASHBACK:
                strategy = CashbackStrategy()
            elif offer_type == PromotionOfferType.FREEBEE:
                strategy = FreebeeStrategy()
            else:
                # Throw error for unsupported offer types
                logger.error(f"Unsupported offer type '{offer_type}' for promotion '{promo_code}'")
                raise HTTPException(
                    status_code=400,
                    detail={"error_code": "UNSUPPORTED_OFFER_TYPE", "message": f"Offer type '{offer_type}' is not supported"}
                )

            # Calculate total discount amount using strategy on eligible cart value
            total_discount = strategy.compute_discount(promotion_doc, eligible_cart_value)

            # Convert eligible items to dict format for strategy
            eligible_items_dict = []
            for item in eligible_items:
                eligible_items_dict.append({
                    "sku": item.sku,
                    "mrp": float(item.mrp),
                    "sale_price": float(item.sale_price),
                    "quantity": item.quantity
                })

            # Apply strategy to eligible items only
            processed_eligible_items = strategy.apply_to_items(eligible_items_dict, total_discount)
            
            # Create a mapping of SKU to processed item for easy lookup
            processed_items_map = {}
            if processed_eligible_items:
                for i, eligible_item in enumerate(eligible_items):
                    if i < len(processed_eligible_items):
                        processed_items_map[eligible_item.sku] = processed_eligible_items[i]
            
            # Build response items for ALL cart items (eligible and non-eligible)
            cart_items_response = []
            for item in items:
                if item.sku in processed_items_map:
                    # This item was eligible and processed
                    processed_item = processed_items_map[item.sku]
                    calculated_sale_price = Decimal(str(processed_item.get("sale_price", item.sale_price)))
                    per_unit_discount = item.sale_price - calculated_sale_price
                    offer_applied = True
                else:
                    # This item was not eligible - no discount applied
                    calculated_sale_price = item.sale_price
                    per_unit_discount = Decimal("0")
                    offer_applied = False

                cart_item_response = CartItemResponse(
                    sku=item.sku,
                    mrp=item.mrp,
                    sale_price=item.sale_price,
                    calculated_sale_price=calculated_sale_price,
                    discount_amount=per_unit_discount,
                    quantity=item.quantity,
                    offer_applied=offer_applied,
                    facility_name=item.facility_name
                )

                cart_items_response.append(cart_item_response)
            
            final_cart_value = cart_value
            if offer_type in [PromotionOfferType.FLAT_DISCOUNT, PromotionOfferType.COUPON]:
                final_cart_value = cart_value - total_discount

            # Prepare response data
            raw_offer_sub_type = promotion_doc.get("offer_sub_type")
            mapped_offer_sub_type = self.map_offer_sub_type(offer_type, raw_offer_sub_type)
            
            response_data = {
                "original_cart_value": cart_value,
                "total_discount_amount": total_discount,
                "final_cart_value": final_cart_value,
                "promotion_code": promo_code,
                "promotion_type": promotion_result.get("promotion_type", ""),
                "offer_sub_type": mapped_offer_sub_type,
                "promotion_facility": facility_name,
                "items": cart_items_response
            }

            if offer_type == PromotionOfferType.FREEBEE:
                freebees_list = freebee.get_freebees(promotion_doc)
                freebee_items = self.process_freebee_items(freebees_list, channel, facility_name, "discount_calculation")
                response_data["freebees"] = freebee_items

            response = CartDiscountResponse(**response_data)

            logger.info(f"calculate_cart_discount_result | original={cart_value} discount={total_discount} final={final_cart_value}")
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"calculate_cart_discount_error | error={e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={"error_code": "INTERNAL_ERROR", "message": "Failed to calculate cart discount"}
            )

    async def validate_cart_items(self, items: List) -> bool:
        """
        Validate cart items for basic requirements
        
        Args:
            items: List of cart items
            
        Returns:
            True if valid, raises HTTPException if invalid
        """
        if not items:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "EMPTY_CART", "message": "Cart cannot be empty"}
            )
        
        for item in items:
            if item.sale_price <= 0:
                raise HTTPException(
                    status_code=400,
                    detail={"error_code": "INVALID_PRICE", "message": f"Invalid sale price for SKU {item.sku}"}
                )
            
            if item.quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail={"error_code": "INVALID_QUANTITY", "message": f"Invalid quantity for SKU {item.sku}"}
                )
        
        return True
