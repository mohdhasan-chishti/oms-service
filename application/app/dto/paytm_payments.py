"""
Paytm payment request/response DTOs for POS system.
"""

from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal


class PaytmPaymentInitiateRequest(BaseModel):
    """Request model for initiating Paytm POS Sale payment
    System automatically calculates unpaid amount for paytm_pos payments.
    """
    order_id: str = Field(..., description="Order ID (displayed on terminal)")
    terminal_id: str = Field(..., description="EDC terminal ID (required)")


class PaytmPaymentStatusRequest(BaseModel):
    """Request model for checking Paytm payment status"""
    txn_id: str = Field(..., description="Paytm transaction ID")
    order_id: str = Field(..., description="OMS order ID")
    terminal_id: str = Field(..., description="EDC terminal ID (required)")


class PaytmPaymentConfirmRequest(BaseModel):
    """Request model for confirming Paytm payment"""
    txn_id: str = Field(..., description="Paytm transaction ID")
    order_id: str = Field(..., description="OMS order ID")
    payment_id: str = Field(..., description="Payment record ID from OMS")
    terminal_id: str = Field(..., description="EDC terminal ID (required)")
