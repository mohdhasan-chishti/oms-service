from pydantic import BaseModel
from typing import List, Optional, Any

class TokenValidationRequest(BaseModel):
    token: str
    customer_id: str

class TokenValidationResponse(BaseModel):
    valid: bool
    message: str

class OrderResponse(BaseModel):
    id: int
    order_id: str
    customer_id: str
    customer_name: str
    facility_id: str
    facility_name: str
    status: int
    total_amount: float
    eta: Optional[str] = None
    order_mode: str
    is_approved: bool
    created_at: str
    updated_at: str

class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    sku: str
    quantity: int
    pos_extra_quantity: float = 0
    unit_price: float
    sale_price: float
    status: int
    created_at: str
    updated_at: str

class OrdersListResponse(BaseModel):
    success: bool
    message: str
    orders: List[OrderResponse]
    total_count: int

class OrderItemsListResponse(BaseModel):
    success: bool
    message: str
    order_items: List[OrderItemResponse]
    total_count: int

class CancelOrderRequest(BaseModel):
    token: str
    customer_id: str
    order_id: str

class CancelOrderResponse(BaseModel):
    success: bool
    message: str
    order_id: Optional[str] = None
