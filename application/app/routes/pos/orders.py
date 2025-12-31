from fastapi import APIRouter, Request, Query, BackgroundTasks
from app.dto.orders import OrderCreate, OrderResponse  # type: ignore
from app.dto.orders import OrderStatusUpdate, OrderItemStatusUpdate  # type: ignore
from app.core.order_functions import (
    create_order_core,
    get_order_details_core,
    get_all_facility_orders_core,
)
from app.core.order_updates import (
    update_order_status_core,
    update_item_status_core,
)
from app.validations.orders import OrderFacilityValidator
from app.dto.phone_validations import validate_phone_number
from app.utils.firebase_utils import get_customer_id_from_phone_number

pos_router = APIRouter(tags=["pos"])


@pos_router.post("/create_order", response_model=OrderResponse)
async def create_order(order: OrderCreate, request: Request, background_tasks: BackgroundTasks):
    """Create order via POS system."""
    biller_id = getattr(request.state, "user_id", "")
    biller_name = getattr(request.state, "user_name", "")
    return await create_order_core(order, request, background_tasks, "pos", biller_id=biller_id, biller_name=biller_name)


@pos_router.get("/order_details")
async def get_order_details(facility_name: str = Query(..., description="Facility name"), order_id: str = Query(..., description="Order ID")):
    """Retrieve order details via POS system."""
    order_validator = OrderFacilityValidator(order_id=order_id, facility_name=facility_name)
    order_validator.validate_order_with_facility()
    return await get_order_details_core(order_id)


@pos_router.get("/orders")
async def get_all_orders(
    facility_name: str = Query(..., description="Facility name"), 
    page_size: int = 20, 
    page: int = 1, 
    sort_order: str = "desc", 
    order_id: str = Query(None, description="Search orders by order ID"),
    phone_number: str = Query(None, description="Filter by phone number"),
    customer_name: str = Query(None, description="Filter by customer name"),
    order_mode: str = Query(None, description="Filter by order mode (app/pos)")
):
    """List orders for a logged-in POS user with optional search functionality."""
    try:
        filters = {}
        customer_id = None
        if phone_number and phone_number.strip():
            validated_phone = validate_phone_number(phone_number.strip())
            customer_id = await get_customer_id_from_phone_number(validated_phone)
            if not customer_id:
                return {
                    "orders": [],
                    "pagination": {
                        "current_page": page,
                        "page_size": page_size,
                        "total_count": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_previous": False
                    },
                    "message": f"No customer found for phone number: {validate_phone_number}"
                }
        filter_params = {
            "order_id": order_id,
            "customer_id": customer_id,
            "customer_name": customer_name, 
            "order_mode": order_mode
        }
        for key, value in filter_params.items():
            if value and str(value).strip():
                filters[key] = str(value).strip()    
        return await get_all_facility_orders_core(facility_name, page_size, page, sort_order, filters)
    except Exception as e:
        return {
            "orders": [],
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_count": 0,
                "total_pages": 0,
                "has_next": False,
                "has_previous": False
            },
            "error": f"Failed to fetch orders: {str(e)}"
        }

# ---- Update endpoints ----
@pos_router.put("/update_order_status")
@pos_router.patch("/update_order_status")
async def update_order_status(order_update: OrderStatusUpdate):
    """Update order status (POS)."""
    return await update_order_status_core(order_update)


@pos_router.put("/update_item_status")
@pos_router.patch("/update_item_status")
async def update_item_status(item_update: OrderItemStatusUpdate):
    """Update item status (POS)."""
    return await update_item_status_core(item_update)
