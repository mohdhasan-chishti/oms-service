from fastapi import APIRouter, Query
from app.core.token_validation_core import (
    get_refund_details_by_phone_number,
)
from app.dto.phone_validations import validate_phone_number

api_router = APIRouter(tags=["api"])

@api_router.get("/refund_details_by_phone")
async def refund_by_phone(phone_number: str = Query(..., description="Phone number (10 digits, 91+10 digits, or +91+10 digits)")):
    # Validate phone number format
    validated_phone = validate_phone_number(phone_number)
    
    return await get_refund_details_by_phone_number(validated_phone)
