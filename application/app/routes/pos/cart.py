from typing import List
from fastapi import APIRouter

# Core functions
from app.core.cart_functions import get_available_promotions_core, calculate_cart_discount_core

# DTOs
from app.dto.cart import PromotionListRequest, PromotionListResponse, CartDiscountRequest, CartDiscountResponse

pos_router = APIRouter(prefix="/cart", tags=["pos-cart"])


@pos_router.post("/promotions/available", response_model=List[PromotionListResponse])
async def get_available_promotions(request: PromotionListRequest):
    """ Get list of available promotions for POS channel """
    return await get_available_promotions_core(request, "pos")


@pos_router.post("/discount/calculate", response_model=CartDiscountResponse)
async def calculate_cart_discount(request: CartDiscountRequest):
    """ Calculate proportional discount for cart items for POS channel """
    return await calculate_cart_discount_core(request, "pos")
