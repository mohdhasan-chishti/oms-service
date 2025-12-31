from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.token_validation_core import (
    validate_token_and_return_items,
    validate_token_and_return_full_order
)
from app.dto.returns import CreateReturnRequest
from app.core.order_return import create_return_core
from app.core.constants import ReturnReasons

api_router = APIRouter(tags=["api"])

class ReturnItemRequest(BaseModel):
    sku: str
    quantity: int

class PartialReturnRequest(BaseModel):
    customer_id: str
    order_id: str
    items: list[ReturnItemRequest]

class FullReturnRequest(BaseModel):
    customer_id: str
    order_id: str

@api_router.post("/return_items")
async def return_items(
    return_request: PartialReturnRequest,
    authorization: str = Header(..., description="Token for authentication")
):
    items_to_return = [{"sku": item.sku, "quantity": item.quantity} for item in return_request.items]
    
    return await validate_token_and_return_items(
        token=authorization,
        customer_id=return_request.customer_id,
        order_id=return_request.order_id,
        items_to_return=items_to_return
    )

@api_router.post("/return_full_order")
async def return_full_order(
    return_request: FullReturnRequest,
    authorization: str = Header(..., description="Token for authentication")
):
    return await validate_token_and_return_full_order(
        token=authorization,
        customer_id=return_request.customer_id,
        order_id=return_request.order_id
    )

@api_router.post("/create_return")
async def create_return(
    req: CreateReturnRequest,
    authorization: str = Header(..., description="Token for authentication")
):
    items_to_return = [{"sku": i.sku, "quantity": i.quantity} for i in (req.items or [])]
    order_full_return = bool(getattr(req, "order_full_return", False))
    order_id = req.order_id
    return_reason = req.return_reason_code if req.return_reason_code else "OTHER"
    comments = req.comments if req.comments else " "
    refund_mode = req.refund_mode if req.refund_mode else None

    try:
        return await create_return_core(
            order_id=order_id,
            items=items_to_return,
            order_full_return=order_full_return,
            return_reason=return_reason,
            comments=comments,
            refund_mode=refund_mode,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
