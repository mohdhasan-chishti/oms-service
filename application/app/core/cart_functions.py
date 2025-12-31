from typing import List, Dict, Optional
from collections import defaultdict
from decimal import Decimal
from fastapi import HTTPException

# Services
from app.cart.service import CartService

# DTOs
from app.dto.cart import (PromotionListRequest, PromotionListResponse,
    CartDiscountRequest, CartDiscountResponse, CartItemResponse
)

# Logging
from app.logging.utils import get_app_logger
logger = get_app_logger("app.core.cart_functions")


async def get_available_promotions_core(request: PromotionListRequest, channel: str) -> List[PromotionListResponse]:
    """
    Core function to get available promotions for any channel
    Returns only the top discount promotion that meets min_purchase requirement

    Args:
        request: PromotionListRequest containing cart details
        channel: Channel identifier (app, pos, etc.)
    Returns:
        List containing only the best applicable promotion (max 1 item)
    """
    try:
        # Force the channel for this request
        request.channel = channel

        # Group items by facility
        facility_groups: Dict[str, List] = defaultdict(list)
        for item in request.items:
            facility_groups[item.facility_name or request.facility_name].append(item)

        applicable_promotions = []

        # Fetch promotions for each facility
        for facility_name, facility_items in facility_groups.items():
            facility_total = sum(item.sale_price * item.quantity for item in facility_items)

            cart_service = CartService()
            promotions = await cart_service.get_available_promotions(
                total_amount=facility_total,
                user_id=request.user_id,
                user_type=request.user_type,
                channel=request.channel,
                facility_name=facility_name,
                payment_modes=request.payment_modes,
                items=facility_items
            )
            # Add facility_name to each promotion and filter applicable ones
            for promo in promotions:
                if promo.is_applicable and promo.min_purchase <= facility_total:
                    promo.facility_name = facility_name
                    applicable_promotions.append(promo)

        # If no applicable promotions found, return empty list
        if not applicable_promotions:
            logger.info(f"{channel}_get_available_promotions_core_response | count=0 | reason=no_applicable_promotions")
            return []

        # For POS channel, return all applicable promotions
        if channel == "pos":
            # Sort by min_purchase (highest first) for consistent ordering
            applicable_promotions.sort(key=lambda x: x.min_purchase, reverse=True)
            logger.info(f"{channel}_get_available_promotions_core_response | count={len(applicable_promotions)} | all_promotions=true")
            return applicable_promotions

        # For APP channel (and others), return only the top promotion
        top_promotion = max(applicable_promotions, key=lambda x: x.min_purchase)

        logger.info(f"{channel}_get_available_promotions_core_response | count=1 | top_promotion={top_promotion.promotion_code} | facility={top_promotion.facility_name} | discount={top_promotion.discount_amount}")
        return [top_promotion]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"{channel}_get_available_promotions_core_error | error={e}", exc_info=True)
        raise HTTPException(status_code=500,
            detail={"error_code": "INTERNAL_ERROR", "message": "Failed to fetch promotions"}
        )


async def calculate_cart_discount_core(request: CartDiscountRequest, channel: str) -> CartDiscountResponse:
    """
    Core function to calculate cart discount for any channel
    Handles multi-facility scenarios by calculating promotion on specific facility items
    but returning all items with original prices for non-promotion facility items
    
    Args:
        request: CartDiscountRequest containing cart items and promotion code
        channel: Channel identifier (app, pos, etc.)

    Returns:
        CartDiscountResponse with calculated discounts per item
    """
    try:
        # Force the channel for this request
        request.channel = channel
        logger.info(f"{channel}_calculate_cart_discount_core | cart_value={request.cart_value} promo_code={request.promo_code} items_count={len(request.items)} facility_name={request.facility_name}")

        cart_service = CartService()
        await cart_service.validate_cart_items(request.items)

        # Determine promotion facility (fallback to request.facility_name)
        promotion_facility = request.promotion_facility or request.facility_name

        # Filter items for promotion facility and calculate total
        promotion_facility_items = []
        other_facility_items = []
        promotion_facility_total = Decimal("0")
        for item in request.items:
            item_facility = item.facility_name or request.facility_name
            if item_facility == promotion_facility:
                promotion_facility_items.append(item)
                promotion_facility_total += item.sale_price * item.quantity
            else:
                other_facility_items.append(item)

        discount_result = await cart_service.calculate_cart_discount(
            cart_value=promotion_facility_total,
            promo_code=request.promo_code,
            items=promotion_facility_items,
            user_id=request.user_id,
            user_type=request.user_type,
            channel=request.channel,
            payment_modes=request.payment_modes,
            facility_name=promotion_facility,
            promotion_type=request.promotion_type
        )

        # Append other facility items as-is (no discount)
        for item in other_facility_items:
            cart_item_response = CartItemResponse(
                sku=item.sku,
                mrp=item.mrp,
                sale_price=item.sale_price,
                calculated_sale_price=item.sale_price,
                discount_amount=Decimal("0"),
                quantity=item.quantity,
                offer_applied=False,
                facility_name=item.facility_name
            )
            discount_result.items.append(cart_item_response)

        # Update totals to include all items
        discount_result.original_cart_value = request.cart_value
        discount_result.final_cart_value = request.cart_value - discount_result.total_discount_amount
        discount_result.promotion_facility = promotion_facility

        logger.info(f"{channel}_calculate_cart_discount_core_response | original={discount_result.original_cart_value} final={discount_result.final_cart_value} discount={discount_result.total_discount_amount} promotion_facility={promotion_facility}")
        return discount_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"{channel}_calculate_cart_discount_core_error | error={e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error_code": "INTERNAL_ERROR", "message": "Failed to calculate discount"}
        )
