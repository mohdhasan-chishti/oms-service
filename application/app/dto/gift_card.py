from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional


class GiftCardRedeemRequest(BaseModel):
    """Request model for gift card redemption"""
    user_id: str = Field(..., description="User ID to credit the gift card amount")


class GiftCardRedeemResponse(BaseModel):
    """Response model for gift card redemption"""
    success: bool = Field(..., description="Whether redemption was successful")
    message: str = Field(..., description="Success or error message")
    amount_added: Optional[Decimal] = Field(None, description="Amount added to wallet")
    new_wallet_balance: Optional[Decimal] = Field(None, description="New wallet balance after redemption")
    gift_card_number: str = Field(..., description="Gift card number that was redeemed")


class GiftCardValidateRequest(BaseModel):
    """Request model for gift card validation"""
    gift_card_number: str = Field(..., description="12-digit alphanumeric gift card number")


class GiftCardValidateResponse(BaseModel):
    """Response model for gift card validation"""
    valid: bool = Field(..., description="Whether gift card is valid")
    gift_card_number: str = Field(..., description="Gift card number")
    amount: Optional[Decimal] = Field(None, description="Gift card amount")
    status: Optional[int] = Field(None, description="Gift card status code")
    status_description: Optional[str] = Field(None, description="Human readable status")
    expires_at: Optional[str] = Field(None, description="Expiry date")
    message: str = Field(..., description="Validation message")
