from fastapi import APIRouter, Request, Query, BackgroundTasks
from app.dto.orders import OrderCreate, OrderResponse  # type: ignore
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

web_router = APIRouter(tags=["web"])


@web_router.post("/create_order", response_model=OrderResponse)
async def create_order(order: OrderCreate, request: Request, background_tasks: BackgroundTasks):
    """Create order via web interface."""
    return await create_order_core(order, request, background_tasks, "web")


@web_router.get("/order_details")
async def get_order_details(order_id: str = Query(..., description="Order ID")):
    """Retrieve order details via web interface."""
    return await get_order_details_core(order_id)


@web_router.get("/orders")
async def get_all_orders(request: Request, page_size: int = 20, page: int = 1, sort_order: str = "desc", search: str = Query(None, description="Search orders by order ID")):
    """List orders for logged-in web user with optional search functionality."""
    return await get_all_orders_core(request, page_size, page, sort_order, search)


# ---- Update endpoints ----

@web_router.put("/update_order_status")
@web_router.patch("/update_order_status")
async def update_order_status(order_update: OrderStatusUpdate):
    """Update order status (web)."""
    return await update_order_status_core(order_update)


@web_router.put("/update_item_status")
@web_router.patch("/update_item_status")
async def update_item_status(item_update: OrderItemStatusUpdate):
    """Update item status (web)."""
    return await update_item_status_core(item_update)
