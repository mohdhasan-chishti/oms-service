import logging
from fastapi import APIRouter, HTTPException, Query
from app.logging.utils import get_app_logger
from app.dto.returns import CreateReturnRequest  # type: ignore
from app.core.order_return import create_return_core
from app.core.constants import ReturnReasons
from app.validations.returns import ReturnsValidator

logger = get_app_logger(__name__)

app_router = APIRouter(tags=["app"])

@app_router.post("/create_return")
async def create_return(req: CreateReturnRequest):
    # Data Extraction
    items_to_return = [{"sku": i.sku,"quantity": i.quantity,"line_reference": i.line_reference} for i in (req.items or [])]
    order_full_return = bool(getattr(req, "order_full_return", False))
    order_id = req.order_id
    
    # Use reason code directly (store codes in DB)
    return_reason = req.return_reason_code if req.return_reason_code else "OTHER"
    comments = req.comments if req.comments else " "
    refund_mode = req.refund_mode if req.refund_mode else None

    # Core Business Logic
    try:
        # Validate order exists and mode matches app origin
        ReturnsValidator.validate_order_for_return(order_id, 'app')
        
        return await create_return_core(
            order_id=order_id,
            items=items_to_return,
            order_full_return=order_full_return,
            return_reason=return_reason,
            comments=comments,
            refund_mode=refund_mode,
        )
    except HTTPException:
        # Let FastAPI render HTTP errors without converting to 500
        raise
    except ValueError as e:
        # Log the full exception with traceback
        logger.warning(f"Validation error in create_return for order {order_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the full exception with traceback
        logger.error(f"Unexpected error in create_return for order {order_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app_router.get("/returns/reasons")
async def get_return_reasons(order_id: str = Query(..., description="Order ID for return reasons")):
    """Get available return reasons for a specific order"""
    try:
        # Validate order exists
        order_service = OrderQueryService()
        order = order_service.get_order_by_id(order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Return available reasons
        return {
            "order_id": order_id,
            "reasons": ReturnReasons.get_all_reasons()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")