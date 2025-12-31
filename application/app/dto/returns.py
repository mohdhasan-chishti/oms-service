from pydantic import BaseModel, Field, condecimal, field_validator, model_validator
from typing import List, Optional, Dict
from app.core.constants import ReturnReasons

from app.logging.utils import get_app_logger
logger = get_app_logger('returns_dto')
# ---- Consolidated DTOs used by app routes and cores ----

class OrderReturnItemRequest(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100, description="SKU of the item to return")
    quantity: condecimal(max_digits=12, decimal_places=3, gt=0) = Field(..., description="Quantity to return (supports fractional quantities up to 3 decimal places)")
    line_reference: Optional[int] = Field(None, description="Reference ID to identify if this was a freebie item")



class CreateReturnRequest(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=50, description="Order ID for return")
    items: Optional[List[OrderReturnItemRequest]] = Field(None, description="Items to return (if provided, treated as partial return)")
    order_full_return: Optional[bool] = Field(False, description="When true and items not provided, process full return")
    return_reason_code: Optional[str] = Field(None, description="Return reason code from predefined list")
    comments: Optional[str] = Field(None, max_length=1000, description="Additional comments for the return request")
    refund_mode: Optional[str] = Field(None, description="Refund mode: 'cash' or 'wallet'")

    @field_validator("return_reason_code")
    def validate_return_reason_code(cls, v):
        if v and v not in ReturnReasons.REASON_DESCRIPTIONS:
            valid_codes = list(ReturnReasons.REASON_DESCRIPTIONS.keys())
            logger.error(f"Invalid return reason code: {v}. Valid codes: {valid_codes}")
            raise ValueError(f"Invalid return reason code. Valid codes: {valid_codes}")
        return v
    
    @field_validator("refund_mode")
    def validate_refund_mode(cls, v):
        if v is not None and v not in ['cash', 'wallet']:
            logger.error(f"Invalid refund_mode: {v}")
            raise ValueError("refund_mode must be either 'cash' or 'wallet'")
        return v

    @model_validator(mode="after")
    def validate_items_or_full_return(self):
        has_items = bool(self.items) and len(self.items) > 0
        has_full = bool(self.order_full_return)
        if not has_items and not has_full:
            logger.error(f"Either items or order_full_return must be provided")
            raise ValueError("Provide non-empty items or set order_full_return=true")
        return self


class OrderReturnResponse(BaseModel):
    success: bool
    message: str
    order_id: str
    return_reference: Optional[str] = Field(None, description="Generated return reference")
    return_type: str = Field(..., description="Type of return: 'partial' or 'full'")
    returned_items: List[Dict] = Field(default_factory=list, description="List of returned items with details")
    total_refund_amount: float = Field(0.0, description="Total refund amount")
    order_status: int
    wms_status: Optional[str] = None
