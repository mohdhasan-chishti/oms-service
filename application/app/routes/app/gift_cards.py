from fastapi import APIRouter, HTTPException, status

# Core functions
from app.core.gift_card_functions import (
    redeem_gift_card_core,
    validate_gift_card_core,
    get_gift_card_details_core
)

# DTOs
from app.dto.gift_card import (
    GiftCardRedeemRequest,
    GiftCardRedeemResponse,
    GiftCardValidateRequest,
    GiftCardValidateResponse
)


app_router = APIRouter(prefix="/gift-cards", tags=["app-gift-cards"])


@app_router.post("/{gift_card_number}/redeem", response_model=GiftCardRedeemResponse)
async def redeem_gift_card(gift_card_number: str, request: GiftCardRedeemRequest):
    """Redeem a gift card for mobile app channel"""
    try:
        response = await redeem_gift_card_core(gift_card_number, request, "app")
        if not response.success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.message
            )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gift card redemption failed: {str(e)}"
        )


@app_router.post("/validate", response_model=GiftCardValidateResponse)
async def validate_gift_card(request: GiftCardValidateRequest):
    """Validate a gift card for mobile app channel"""
    try:
        return await validate_gift_card_core(request, "app")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gift card validation failed: {str(e)}"
        )


@app_router.get("/{gift_card_number}")
async def get_gift_card_details(gift_card_number: str):
    """Get gift card details for mobile app channel"""
    try:
        return await get_gift_card_details_core(gift_card_number, "app")
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get gift card details: {str(e)}"
            )
