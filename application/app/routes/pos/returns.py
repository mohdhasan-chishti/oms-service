from fastapi import APIRouter, HTTPException

from app.core.order_return import create_return_core
from app.dto.returns import CreateReturnRequest
from app.logging.utils import get_app_logger
from app.validations.returns import ReturnsValidator

pos_router = APIRouter(tags=["pos"])
logger = get_app_logger(__name__)

@pos_router.post("/create_return")
async def pos_create_return(req: CreateReturnRequest):
     """
     POS-compatible create_return endpoint mirroring the App's behavior.
     Accepts the same payload as /app/v1/create_return and delegates to core.
     """
     # Data Extraction (same as app route)
     items_to_return = [{"sku": i.sku, "quantity": i.quantity,"line_reference": i.line_reference} for i in (req.items or [])]
     order_full_return = bool(getattr(req, "order_full_return", False))
     order_id = req.order_id
     return_reason = req.return_reason_code if req.return_reason_code else "OTHER"
     comments = req.comments if req.comments else " "
     refund_mode = req.refund_mode if req.refund_mode else None

     try:
         # Validate order exists and mode matches POS origin
         ReturnsValidator.validate_order_for_return(order_id, 'pos')
         
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
     except ValueError as e:
         logger.warning(f"Validation error in POS create_return for order {order_id}: {str(e)}")
         raise HTTPException(status_code=400, detail=str(e))
     except Exception as e:
         logger.error(
             f"Unexpected error in POS create_return for order {order_id}: {str(e)}",
             exc_info=True,
         )
         raise HTTPException(status_code=500, detail="Internal server error")
