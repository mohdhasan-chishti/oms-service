from typing import List, Dict
from fastapi import APIRouter
from pydantic import BaseModel

# Core functions
from app.core.cart_functions import get_available_promotions_core, calculate_cart_discount_core

# DTOs
from app.dto.cart import PromotionListRequest, PromotionListResponse, CartDiscountRequest, CartDiscountResponse

# Validation
from app.validations.order_promotion_validation import OrderPromotionValidator

app_router = APIRouter(prefix="/cart", tags=["app-cart"])


@app_router.post("/promotions/available", response_model=List[PromotionListResponse])
async def get_available_promotions(request: PromotionListRequest):  
    """ Get list of available promotions for mobile app channel """
    return await get_available_promotions_core(request, "app")


@app_router.post("/discount/calculate", response_model=CartDiscountResponse)
async def calculate_cart_discount(request: CartDiscountRequest):
    """ Calculate proportional discount for cart items for mobile app channel """
    return await calculate_cart_discount_core(request, "app")


class PromotionTestRequest(BaseModel):
    promotion_code: str
    facility_name: str
    user_id: str
    channel: str = "app"
    payment_modes: List[str] = ["online"]
    items: List[Dict]


@app_router.post("/test/promotion-discount")
async def test_promotion_discount_calculation(request: PromotionTestRequest):
    """ Test endpoint to compare promotion engine vs cart service discount calculations """
    return await OrderPromotionValidator.test_promotion_discount_calculation(
        order_items=request.items,
        promotion_code=request.promotion_code,
        facility_name=request.facility_name,
        user_id=request.user_id,
        channel=request.channel,
        payment_modes=request.payment_modes
    )
