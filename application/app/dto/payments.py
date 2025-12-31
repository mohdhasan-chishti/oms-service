"""
Payment-related Data Transfer Objects (DTOs) for Razorpay integration.

This module contains Pydantic models for payment requests, responses,
and webhook data structures.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class PaymentOrderCreate(BaseModel):
    """Request model for creating a payment order"""
    order_id: str = Field(..., min_length=1, max_length=50, description="OMS Order ID")
    amount: float = Field(..., gt=0, description="Order amount in rupees")
    customer_id: str = Field(..., min_length=1, max_length=50)
    customer_name: Optional[str] = Field(None, max_length=100)
    customer_email: Optional[str] = Field(None, description="Customer email for receipts")
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    notes: Optional[Dict[str, Any]] = Field(None, description="Additional notes")


class PaymentOrderResponse(BaseModel):
    """Response model for payment order creation"""
    success: bool
    message: str
    razorpay_order_id: Optional[str] = None
    amount: Optional[float] = None
    amount_paise: Optional[int] = None
    currency: Optional[str] = None
    key_id: Optional[str] = None
    order_id: Optional[str] = None
    created_at: Optional[int] = None
    error: Optional[str] = None


class PaymentVerification(BaseModel):
    """Request model for payment verification"""
    razorpay_order_id: str = Field(..., description="Razorpay order ID")
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID")
    razorpay_signature: str = Field(..., description="Razorpay signature for verification")
    oms_order_id: str = Field(..., description="OMS order ID")


class PaymentVerificationResponse(BaseModel):
    """Response model for payment verification"""
    success: bool
    message: str
    verified: Optional[bool] = None
    order_id: Optional[str] = None
    payment_status: Optional[str] = None
    error: Optional[str] = None


class WebhookPayload(BaseModel):
    """Model for Razorpay webhook payload"""
    event: str = Field(..., description="Webhook event type")
    account_id: str = Field(..., description="Razorpay account ID")
    entity: Dict[str, Any] = Field(..., description="Payment/Order entity data")
    contains: list = Field(..., description="List of entities in the webhook")
    created_at: int = Field(..., description="Webhook creation timestamp")


class PaymentStatus(BaseModel):
    """Model for payment status information"""
    payment_id: str
    order_id: str
    oms_order_id: str
    status: str
    amount: int
    currency: str
    method: Optional[str] = None
    captured: bool
    created_at: int
    updated_at: Optional[int] = None


class PaymentStatusUpdate(BaseModel):
    """Request model for updating payment status"""
    order_id: str = Field(..., description="OMS Order ID")
    payment_id: str = Field(..., description="Razorpay payment ID")
    status: str = Field(..., description="Payment status")
    amount: Optional[float] = None
    notes: Optional[Dict[str, Any]] = None
