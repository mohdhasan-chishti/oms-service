from fastapi import HTTPException
from app.connections.database import get_raw_transaction
from app.services.order_service import OrderService
from app.core.constants import OrderStatus
from sqlalchemy import text
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone

# Services
from app.services.returns_service import ReturnsService
from app.integrations.potions_service import PotionsService

# Validators
from app.validations.returns import ReturnsValidator

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("app.core.order_return")


async def create_return_core(order_id: str, items: Optional[List[Dict]] = None, order_full_return: bool = False, return_reason: Optional[str] = None, comments: Optional[str] = None, refund_mode: Optional[str] = None):
    """
    Behavior:
    - If items are provided (non-empty): treat as partial return and return only those SKUs/quantities.
    - Else if order_full_return is True: fetch eligible items from DB and return them all (based on fulfilled statuses).
    - Else: 400 Bad Request.

    Args:
        order_id: OMS order ID
        items: Optional list of {sku, quantity} for partial return
        order_full_return: When true and items not provided, process full return
        return_reason: Optional reason code
        comments: Optional free-text comments to store with the return
        refund_mode: Optional refund mode ('cash' or 'wallet')
    """
    logger.info(f"return_request_processing | order_id={order_id} return_type={'full' if order_full_return else 'partial'}")
    try:
        # Prepare items for full return if requested
        if order_full_return and not items:
            items = OrderService.get_return_eligible_items(order_id)  # may raise ValueError

        # Validate Layer
        with get_raw_transaction() as conn:
            # Ensure order exists and status allows returns (may raise ValueError)
            order_row, facility_name = ReturnsValidator.validate_order_exists_and_status(conn, order_id)

            # Build current_items map for existence/quantity checks
            get_items_sql = """
                SELECT id, sku, quantity, fulfilled_quantity, delivered_quantity, status, is_returnable, return_type, return_window
                FROM order_items
                WHERE order_id = :order_pk
            """
            items_result = conn.execute(text(get_items_sql), {'order_pk': order_row.id})
            current_items = {row.sku: row for row in items_result.fetchall()}

            # Pre-compute already returned quantities per SKU for this order
            already_returned: dict[str, int] = {}
            prior_sql = """
                SELECT ri.sku AS sku, SUM(ri.quantity_returned) AS qty
                FROM returns r
                JOIN return_items ri ON ri.return_id = r.id
                WHERE r.order_id = :order_pk
                GROUP BY ri.sku
            """
            prior_rows = conn.execute(text(prior_sql), { 'order_pk': order_row.id }).fetchall()
            for prior_row in prior_rows:
                already_returned[str(prior_row.sku)] = int(prior_row.qty)

            # When items are provided (partial) or derived (full), validate them (may raise ValueError)
            if items and len(items) > 0:
                matched_rows = ReturnsValidator.validate_items_exist_and_quantities(current_items, items, already_returned)
                ReturnsValidator.validate_items_eligibility(matched_rows)

            # Cache current status name before exiting DB context
            current_status_name = OrderStatus.get_customer_status_name(order_row.status)
            order_mode = order_row.order_mode

        # If we have items persist return and respond
        if items and len(items) > 0:
            persisted = ReturnsService.create_return(order_id, items, return_reason, comments, refund_mode)
            # Trigger appropriate Potions WMS action based on order mode
            potions_service = PotionsService()
            if order_mode != 'pos':
                # For non-POS orders: trigger reverse consignment
                potions_result = await potions_service.create_reverse_consignment_by_return_reference(
                    persisted["return_reference"], order_id
                )
                wms_status = potions_result.data.get("status", "unknown") if getattr(potions_result, "data", None) else "unknown"
            else:
                # For POS orders: trigger sales return
                potions_result = await potions_service.create_sales_return(
                    persisted["return_reference"], facility_name
                )
                wms_status = potions_result.data.get("status", "unknown") if getattr(potions_result, "data", None) else "unknown"
            ret_type = "full" if order_full_return else "partial"
            return {
                "success": True,
                "message": f"Return created for order {order_id}",
                "order_id": order_id,
                "return_reference": persisted["return_reference"],
                "return_type": ret_type,
                "returned_items": persisted["returned_items"],
                "total_refund_amount": persisted["total_refund_amount"],
                "order_status": current_status_name,
                "wms_status": wms_status,
            }

        # Full return path fallback: if flag set but no items resolved/eligible
        if order_full_return:
            raise HTTPException(status_code=400, detail="No eligible items found to return for this order")

        # Neither items nor full-return flag provided
        raise HTTPException(status_code=400, detail="Provide items for partial return or set order_full_return=true for full return")
    except HTTPException as http_exc:
        logger.warning(f"return_processing_http_exception | order_id={order_id} status_code={http_exc.status_code}",exc_info=True,)
        raise
    except ValueError as e:
        logger.warning(f"return_processing_validation_error | order_id={order_id} error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"return_processing_unexpected_error | order_id={order_id} error={str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")