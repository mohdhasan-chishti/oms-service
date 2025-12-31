from fastapi import APIRouter, Query, Header, Request, BackgroundTasks
from pydantic import BaseModel, field_validator
from typing import Optional

from app.core.token_validation_core import (
    validate_token_and_get_orders,
    validate_token_and_get_order_items,
    validate_token_and_cancel_order,
    get_orders_by_phone_number,
)
from app.core.order_functions import get_all_orders_core, get_order_details_core, create_order_core
from app.dto.phone_validations import validate_phone_number
from app.core.invoices import get_invoice_url_core
from app.core.order_cancel import get_cancel_reasons_core
from app.core.constants import CancelReasons
from app.dto.orders import OrderCreate, OrderResponse
from app.logging.utils import get_app_logger

logger = get_app_logger('api_orders')

api_router = APIRouter(tags=["api"])

class CancelOrderRequest(BaseModel):
    customer_id: str
    order_id: str
    cancel_reason: Optional[str] = ''
    cancel_remarks: Optional[str] = ''

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
            if not v or v.strip() == "":
                logger.error("cancel_remarks is required and must not be empty when cancel_reason is 'OTHER'")
                raise ValueError("cancel_remarks is required and must not be empty when cancel_reason is 'OTHER'")
            return v.strip()
        else:
            return ''

@api_router.post("/create_order", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(..., description="Token for authentication"),
):
    """Create order via API with token-based authentication."""
    return await create_order_core(order, request, background_tasks, "api")

@api_router.get("/get_orders")
async def get_orders(
    customer_id: str = Query(..., description="Customer ID"),
    page_size: int = Query(20, description="Number of orders to return per page"),
    page: int = Query(1, description="Page number (starting from 1)"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    search: str = Query(None, description="Search orders by order ID"),
    authorization: str = Header(..., description="Token for authentication")
):
    return await validate_token_and_get_orders(
        token=authorization,
        customer_id=customer_id,
        page_size=page_size,
        page=page,
        sort_order=sort_order,
        search=search
    )

@api_router.get("/get_orders_by_phone_number")
async def get_orders_by_phone(
    phone_number: str = Query(..., description="Phone number (10 digits, 91+10 digits, or +91+10 digits)"),
    page_size: int = Query(20, description="Number of orders to return per page"),
    page: int = Query(1, description="Page number (starting from 1)"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    search: str = Query(None, description="Search orders by order ID"),
    authorization: str = Header(..., description="Token for authentication")
):
    # Validate phone number format
    validated_phone = validate_phone_number(phone_number)
    
    return await get_orders_by_phone_number(
        phone_number=validated_phone,
        page_size=page_size,
        page=page,
        sort_order=sort_order,
        search=search
    )

@api_router.get("/order_details")
async def get_order_details(order_id: str = Query(..., description="Order ID")):
    return await get_order_details_core(order_id)

@api_router.get("/order_items")
async def get_order_items(
    customer_id: str = Query(..., description="Customer ID"),
    order_id: str = Query(..., description="Order ID to get items for"),
    authorization: str = Header(..., description="Token for authentication")
):
    return await validate_token_and_get_order_items(
        token=authorization,
        customer_id=customer_id,
        order_id=order_id
    )

@api_router.post("/cancel_order")
async def cancel_order(
    cancel_request: CancelOrderRequest,
    authorization: str = Header(..., description="Token for authentication")
):
    return await validate_token_and_cancel_order(
        token=authorization,
        customer_id=cancel_request.customer_id,
        order_id=cancel_request.order_id,
        cancel_reason=cancel_request.cancel_reason,
        cancel_remarks=cancel_request.cancel_remarks
    )


@api_router.get("/cancel_reasons")
async def get_cancel_reasons(authorization: str = Header(..., description="Token for authentication")):
    """Get list of predefined cancellation reasons."""
    return get_cancel_reasons_core()


@api_router.get("/invoice_url")
async def get_invoice_url(customer_id: str = Query(..., description="User ID"), invoice_s3_url: str = Query(..., description="Invoice S3 URL/Key"), order_id: str = Query(..., description="Order ID")):
    return await get_invoice_url_core(customer_id,invoice_s3_url, order_id)
