from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional
from datetime import datetime
import re
from app.logging.utils import get_app_logger
from app.repository.payments import PaymentRepository
from app.core.constants import CancelReasons

logger = get_app_logger('orders_dto')

class OrderItemCreate(BaseModel):
    id: Optional[str] = Field(None, max_length=100, description="Product ID from Typesense")
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field("Product", max_length=200, description="Item name")
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., gte=0)
    sale_price: float = Field(..., gte=0)
    original_sale_price: Optional[float] = Field(None, gte=0, description="Original sale price before any discounts")
    pos_extra_quantity: float = Field(0, gte=0, description="Additional quantity added via POS")
    category: Optional[str] = Field(None, description="Primary category (e.g., 'Groceries')")
    sub_category: Optional[str] = Field(None, description="Sub category (e.g., 'Dairy Products')")
    sub_sub_category: Optional[str] = Field(None, description="Sub-sub category (e.g., 'Milk & Cream')")
    is_freebee: bool = Field(False, description="Flag indicating if this item is a freebee from promotion")
    marketplace: Optional[str] = Field("ROZANA", max_length=32, description="Marketplace name")
    referral_id: Optional[str] = Field("", max_length=32, description="Referral ID")
    facility_name: Optional[str] = Field("", max_length=100, description="Facility name")

    def model_post_init(self, __context) -> None:
        """Set original_sale_price to sale_price if not provided"""
        if self.original_sale_price is None:
            self.original_sale_price = self.sale_price


class PaymentInfo(BaseModel):
    payment_mode: str = Field(..., description="Payment mode: 'cash', 'razorpay', 'cod', 'online', 'paytm_pos'")
    create_payment_order: bool = Field(False, description="Create payment order for online payments")
    amount: Optional[float] = Field(None, description="Amount for this payment mode")
    terminal_id: Optional[str] = Field(None, description="Required when payment_mode is 'paytm_pos'")

    @field_validator("payment_mode", mode="before")
    def validate_payment_mode(cls, payment_mode):
        """Validate payment_mode is in allowed list"""
        # Allow all payment modes, gateways, and the special "payment_gateway" key
        allowed = {"cash", "razorpay", "cashfree", "paytm", "cod", "wallet", "online", "payment_gateway", "paytm_pos"}
        if payment_mode.lower() not in allowed:
            logger.error(f"Invalid payment_mode: {payment_mode}")
            raise ValueError(f"Invalid payment_mode: {payment_mode}")
        return payment_mode.lower()

    @field_validator("create_payment_order")
    def validate_create_payment_order(cls, v, info):
        """Validate create_payment_order based on payment mode"""
        payment_mode = info.data.get("payment_mode", "").lower()
        
        # Payment modes that require create_payment_order=true
        requires_order = {"razorpay", "cashfree", "wallet", "payment_gateway", "paytm_pos"}
        if payment_mode in requires_order and not v:
            logger.error(f"create_payment_order must be true for {payment_mode}")
            raise ValueError(f"create_payment_order must be true for {payment_mode}")
        
        # Payment modes that require create_payment_order=false
        requires_no_order = {"cash", "online", "cod"}
        if payment_mode in requires_no_order and v:
            logger.error(f"create_payment_order must be false for {payment_mode}")
            raise ValueError(f"create_payment_order must be false for {payment_mode}")

        return v

    @field_validator("amount", mode="after")
    def validate_amount_for_payment_gateway(cls, v, info):
        payment_mode = info.data.get("payment_mode", "").lower()
        if payment_mode == "payment_gateway" and (v is None or v < 1.0):
            logger.error("Payment amount must be at least 1 rupee for payment_gateway mode")
            raise ValueError("Payment amount must be at least 1 rupee for online mode")
        return v


class OrderAddress(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=20)
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: str = Field("default city", max_length=100)
    state: str = Field("default state", max_length=50)
    postal_code: str = Field(..., min_length=1, max_length=10)
    country: str = "india"
    type_of_address: str
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude coordinate (between -180 and 180)")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude coordinate (between -90 and 90)")

    @field_validator("type_of_address")
    def validate_type(cls, v):
        allowed = {"work", "home", "other"}
        if v.lower() not in allowed:
            logger.error(f"Invalid type_of_address: {v}")
            raise ValueError("type_of_address must be one of: 'work', 'home', 'other'")
        return v

    @field_validator("phone_number")
    def validate_phone(cls, v):
        pattern = r"^(\+\d{1,2}\s?)?1?\-?\s?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}$"
        if not re.fullmatch(pattern, v):
            logger.error(f"Invalid phone number format: {v}")
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("longitude")
    def validate_longitude(cls, v):
        if v is not None and (v < -180 or v > 180):
            logger.error(f"Invalid longitude: {v}")
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("latitude")
    def validate_latitude(cls, v):
        if v is not None and (v < -90 or v > 90):
            logger.error(f"Invalid latitude: {v}")
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("city")
    def validate_city(cls, v):
        if not v or v.strip() == "":
            return "default city"
        return v

    @field_validator("state")
    def validate_state(cls, v):
        if not v or v.strip() == "":
            return "default state"
        return v
    
class MetaData(BaseModel):
    device_id : str = Field("", min_length=1, max_length=128)
    longitude : float = Field(0.0, ge=-180, le=180, description="Longitude coordinate (between -180 and 180)")
    latitude : float = Field(0.0, ge=-90, le=90, description="Latitude coordinate (between -90 and 90)")


class OrderCreate(BaseModel):
    customer_id: Optional[str] = Field(None, min_length=1, max_length=50)
    customer_name: Optional[str] = Field(None, max_length=100)
    facility_id: str = Field(..., min_length=1, max_length=50)
    facility_name: str = Field(..., min_length=1, max_length=100)
    status: str = Field("pending", pattern="^(pending|confirmed|delivered|cancelled)$")
    total_amount: float = Field(..., gt=0)
    is_approved: bool = Field(True)
    items: List[OrderItemCreate]
    address: OrderAddress
    payment: List[PaymentInfo] = Field(..., min_items=1, description="List of payment information for multiple payment modes")    
    # Payment integration fields (backward compatibility)
    customer_email: Optional[str] = Field(None, description="Customer email for payment order")
    customer_phone: Optional[str] = Field(None, description="Customer phone for payment order")
    eta : Optional[str] = Field(None, description="Estimated time of arrival")
    eta_data: Optional[Dict[str, str]] = Field(None, description="Facility-specific ETAs")
    promotion_code: Optional[str] = Field(None, max_length=50, description="promotion code")
    promotion_type: Optional[str] = Field("cashback", max_length=50, description="promotion type")
    promotion_facility: Optional[str] = Field(None, max_length=100, description="facility name for promotion validation")
    user_type: str = Field("customer", max_length=100, description="Type of user (e.g., 'customer', 'employee', 'distributor', 'peer')")
    version: Optional[str] = Field("", max_length=50, description="Application version that created the order")
    marketplace: Optional[str] = Field("ROZANA", max_length=32, description="Marketplace name")
    referral_id: Optional[str] = Field("", max_length=32, description="Referral ID")
    metadata: Optional[MetaData] = Field(default_factory=MetaData, description="Additional metadata")
    order_charges: Optional[Dict[str, Dict[str, float]]] = Field(None, description="Facility-wise delivery and packaging charges")

    @field_validator("promotion_type")
    def validate_promotion_type(cls, v):
        if v is not None and v not in ["cashback", "flat_discount", "freebee", "coupon"]:
            logger.error(f"Invalid promotion_type: {v}")
            raise ValueError(f"promotion_type must be one of: 'cashback' or 'flat_discount' or 'freebee' or 'coupon', got: {v}")
        return v

    @field_validator("payment", mode="after")
    def transform_payment_gateway(cls, payment_list, info):
        """Transform payment_mode from 'payment_gateway' to actual gateway from database"""
        facility_name = info.data.get("facility_name")
        if not facility_name:
            return payment_list

        payment_repo = PaymentRepository()
        for payment in payment_list:
            if payment.payment_mode.lower() == "payment_gateway":
                # Query database for actual gateway
                actual_gateway = payment_repo.get_active_payment_gateway_for_facility(facility_name)
                if actual_gateway:
                    logger.info(f"transform_payment_gateway | facility_name={facility_name} gateway={actual_gateway}")
                    payment.payment_mode = actual_gateway
                else:
                    # Default to cashfree if not found
                    logger.info(f"transform_payment_gateway | facility_name={facility_name} using_default=cashfree")
                    payment.payment_mode = "cashfree"

        return payment_list


class OrderStatusUpdate(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=50)
    status: str = Field(..., pattern="^(pending|confirmed|delivered|cancelled)$")

class OrderItemStatusUpdate(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=50)
    sku: str = Field(..., min_length=1, max_length=100)
    status: str = Field(..., pattern="^(pending|confirmed|delivered|cancelled|refunded)$")

class OrderCancelRequest(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=50, description="Order ID to cancel")
    cancel_reason: Optional[str] = Field('', max_length=100, description="Reason for cancellation (optional for backward compatibility)")
    cancel_remarks: Optional[str] = Field('', max_length=255, description="Additional remarks for cancellation")

    @field_validator("cancel_reason")
    def validate_cancel_reason(cls, v):
        """
        Validate that cancel_reason is one of the predefined constants.
        Empty string is allowed for backward compatibility.
        """
        if v and v.strip():  # Only validate if reason is provided
            valid_reasons = list(CancelReasons.REASON_DESCRIPTIONS.keys())
            if v not in valid_reasons:
                logger.error(f"Invalid cancel_reason: {v}. Valid reasons are: {valid_reasons}")
                raise ValueError(f"Invalid cancel_reason. Must be one of: {valid_reasons}")
        return v

    @field_validator("cancel_remarks")
    def validate_cancel_remarks(cls, v, info):
        """
        Validate cancel_remarks based on cancel_reason:
        - If cancel_reason is 'OTHER': cancel_remarks must be a non-empty string
        - For all other reasons: cancel_remarks defaults to empty string
        - If cancel_reason is empty (older frontend): both fields default to empty string
        """
        cancel_reason = info.data.get("cancel_reason", '')
        
        # If cancel_reason is provided and is 'OTHER', remarks must be provided
        if cancel_reason == CancelReasons.OTHER:
            # For 'OTHER', remarks must be provided and not empty
            if not v or v.strip() == "":
                logger.error("cancel_remarks is required and must not be empty when cancel_reason is 'OTHER'")
                raise ValueError("cancel_remarks is required and must not be empty when cancel_reason is 'OTHER'")
            return v.strip()
        else:
            # For all other reasons, set to empty string
            return ''

class OrderCancelResponse(BaseModel):
    success: bool
    message: str
    order_id: str
    status: str
    wms_status: Optional[str] = None

## Return-related DTOs moved to app/dto/returns.py

class OrderResponse(BaseModel):
    success: bool
    message: str
    order_id: str
    eta: Optional[str] = None  # Changed from datetime to str for readable format
    multi_order: Optional[bool] = Field(None, description="if order is multi-facility order")

    # Payment order details (when auto_create_payment_order=True)
    payment_order_details: Optional[List[Dict]] = Field(None, description="List of Razorpay payment order details")
    applied_promotion: Optional[Dict] = Field(None, description="Details of applied promotion")
    application_environment: Optional[str] = Field(None, description="Application environment")