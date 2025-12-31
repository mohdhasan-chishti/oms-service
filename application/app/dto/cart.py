from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class FreebeeItem(BaseModel):
    """Freebee item model for promotions"""
    child_sku: str = Field(..., description="SKU of the freebee item")
    selling_price: Decimal = Field(..., description="Selling price of the freebee item")

class CartItem(BaseModel):
    """Cart item model"""
    sku: str
    mrp: Decimal
    sale_price: Decimal  # This represents the original price (before promotion discounts)
    quantity: Decimal = Field(default=1, description="Item quantity (supports decimal values)")
    # Category fields for category-level promotions - UI should always send all three levels
    category: Optional[str] = Field(None, description="Primary category (e.g., 'Groceries')")
    sub_category: Optional[str] = Field(None, description="Sub category (e.g., 'Dairy Products')")
    sub_sub_category: Optional[str] = Field(None, description="Sub-sub category (e.g., 'Milk & Cream')")
    facility_name: Optional[str] = Field(None, description="Facility name for multi-facility cart")


class PromotionListRequest(BaseModel):
    """Request model for listing available promotions"""
    total_amount: Decimal = Field(..., description="Total cart amount")
    user_id: Optional[str] = Field(None, description="User ID for personalized promotions")
    user_type: str = Field("customer", description="Type of user (e.g., 'customer', 'employee', 'distributor', 'peer')")
    channel: str = Field(default="app", description="Sales channel (app, pos)")
    payment_modes: List[str] = Field(default=["online"], description="Available payment modes")
    facility_name: str = Field(..., description="Facility code for facility-specific promotions")
    items: List[CartItem] = Field(..., description="List of cart items with category information")


class PromotionListResponse(BaseModel):
    """Response model for promotion listing"""
    promotion_code: str
    title: str
    description: str
    offer_type: str
    discount_amount: Decimal
    min_purchase: Optional[Decimal]
    is_applicable: bool
    promotion_facility: str = Field(..., description="Facility name")
    freebees: List[FreebeeItem] = Field(default_factory=list, description="List of freebee items for freebee promotions")
    facility_name: Optional[str] = Field(None, description="Facility name for facility-specific promotions")


class CartDiscountRequest(BaseModel):
    cart_value: Decimal = Field(..., description="Total cart value")
    promo_code: str = Field(..., description="Promotion code to apply")
    promotion_type: Optional[str] = Field(None, description="Promotion type hint (coupon, flat_discount, cashback, freebee)")
    promotion_facility: Optional[str] = Field(None, description="Facility name for facility-specific promotions")
    items: List[CartItem] = Field(..., description="List of cart items")
    user_id: str = Field(..., description="User ID")
    user_type: str = Field("customer", description="Type of user (e.g., 'customer', 'employee', 'distributor', 'peer')")
    channel: str = Field(default="app", description="Sales channel")
    payment_modes: List[str] = Field(default=["online"], description="Payment modes")
    facility_name: str = Field(..., description="Facility name for facility-specific promotions")


class CartItemResponse(BaseModel):
    """Response model for cart item with calculated discount"""
    sku: str
    mrp: Decimal
    sale_price: Decimal
    calculated_sale_price: Decimal
    discount_amount: Decimal
    quantity: Decimal
    facility_name: Optional[str] = Field(None, description="Facility name for facility-specific promotions")
    offer_applied: bool = Field(..., description="Whether the promotion was applied to this item")


class CartDiscountResponse(BaseModel):
    """Response model for cart discount calculation"""
    original_cart_value: Decimal
    total_discount_amount: Decimal
    final_cart_value: Decimal
    promotion_code: str
    promotion_type: str
    offer_sub_type: Optional[str] = Field(None, description="Discount sub-type: amount or percentage")
    promotion_facility: str = Field(..., description="Facility name")
    items: List[CartItemResponse]
    freebees: Optional[List[FreebeeItem]] = Field(None, description="List of freebee items for freebee promotions")
