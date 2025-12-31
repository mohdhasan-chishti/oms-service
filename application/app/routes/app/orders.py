from fastapi import APIRouter, Request, Query, BackgroundTasks
from app.dto.orders import OrderCreate, OrderResponse, OrderCancelRequest, OrderCancelResponse  # type: ignore
from app.dto.order_again import OrderAgainResponse
from app.dto.encryption import EncryptCustomerCodeRequest, EncryptCustomerCodeResponse
from app.services.order_query_service import OrderQueryService
from app.dto.orders import OrderStatusUpdate, OrderItemStatusUpdate  # type: ignore
from app.core.order_functions import (
    create_order_core,
    get_order_details_core,
    get_all_orders_core,
)

from app.core.order_updates import (
    update_order_status_core,
    update_item_status_core,
)
from app.core.order_cancel import cancel_order_core, get_cancel_reasons_core
from app.core.encryption_core import encrypt_customer_code_core
from app.core.invoices import get_invoice_url_core
from app.validations.orders import OrderUserValidator

app_router = APIRouter(tags=["app"])


@app_router.post("/create_order", response_model=OrderResponse)
async def create_order(order: OrderCreate, request: Request, background_tasks: BackgroundTasks):
    """Create order via mobile app."""
    return await create_order_core(order, request, background_tasks, "app")


@app_router.get("/order_details")
async def get_order_details(request: Request, order_id: str = Query(..., description="Order ID")):
    """Retrieve single order details via mobile app."""
    user_id = getattr(request.state, "user_id", None)
    order_validator = OrderUserValidator(order_id=order_id, user_id=user_id)
    order_validator.validate_order_with_user()
    return await get_order_details_core(order_id, user_id)


@app_router.get("/orders")
async def get_all_orders(request: Request, page_size: int = 20, page: int = 1, sort_order: str = "desc", 
    search: str = Query(None, description="Search orders by order ID"),
    exclude_status = Query(None, description="Exclude orders with this status"),
    current_order_limit = Query(None, description="Threshold for fetching legacy orders"),
    ph_number: str = Query(None, alias="phone_number", description="Filter by phone number"),
    user_type: str = Query(None, description="Filter by user type")
):
    """List orders for logged-in mobile user with optional search functionality."""
    user_id = getattr(request.state, "user_id", None)
    return await get_all_orders_core(user_id, page_size, page, sort_order, search, exclude_status, current_order_limit, ph_number, user_type)


@app_router.get("/order_again", response_model=OrderAgainResponse)
async def order_again(request: Request, page_size: int = 20, page: int = 1):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return OrderAgainResponse(products=[])

    service = OrderQueryService()
    result = service.get_order_again_products(user_id=user_id, page_size=page_size, page=page)
    return OrderAgainResponse(products=result.get("products", []))

# ---- Update endpoints ----
@app_router.put("/update_order_status")
@app_router.patch("/update_order_status")
async def update_order_status(order_update: OrderStatusUpdate):
    """Update order status (mobile)."""
    return await update_order_status_core(order_update)


@app_router.put("/update_item_status")
@app_router.patch("/update_item_status")
async def update_item_status(item_update: OrderItemStatusUpdate):
    """Update individual item status (mobile)."""
    return await update_item_status_core(item_update)


@app_router.post("/cancel_order", response_model=OrderCancelResponse)
async def cancel_order(cancel_request: OrderCancelRequest, request: Request):
    """Cancel order with reason and remarks validation."""
    user_id = getattr(request.state, "user_id", None)
    order_validator = OrderUserValidator(order_id=cancel_request.order_id, user_id=user_id)
    order_validator.validate_order_with_user()
    return await cancel_order_core(cancel_request.order_id, cancel_request.cancel_reason, cancel_request.cancel_remarks)


@app_router.get("/cancel_reasons")
async def get_cancel_reasons():
    """Get list of predefined cancellation reasons."""
    return get_cancel_reasons_core()


@app_router.post("/encrypt_customer_code", response_model=EncryptCustomerCodeResponse)
async def encrypt_customer_code(request_data: EncryptCustomerCodeRequest, request: Request):
    """Encrypt customer code using AES encryption with Firebase token validation."""
    return await encrypt_customer_code_core(request_data.customer_code, request)

@app_router.get("/invoice_url")
async def get_invoice_url(request: Request, invoice_s3_url: str = Query(..., description="Invoice S3 URL/Key"), order_id: str = Query(..., description="Order ID")):
    user_id = getattr(request.state, "user_id", None)
    return await get_invoice_url_core(user_id,invoice_s3_url, order_id)
