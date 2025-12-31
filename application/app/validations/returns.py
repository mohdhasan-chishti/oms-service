from typing import List, Dict, Tuple
from sqlalchemy import text
from app.core.constants import OrderStatus
from app.services.order_query_service import OrderQueryService

from app.logging.utils import get_app_logger
logger = get_app_logger('returns_validations')

class ReturnsValidator:
    # Returns are eligible only after delivery
    allowed_order_statuses = [
        OrderStatus.TMS_DELIVERED,
        OrderStatus.TMS_PARTIAL_DELIVERED,
    ]

    @staticmethod
    def validate_order_exists_and_status(conn, order_id: str) -> Tuple[object, str]:
        check_order_sql = """
            SELECT id, order_id, status, facility_name, order_mode
            FROM orders
            WHERE order_id = :order_id
        """
        result = conn.execute(text(check_order_sql), {'order_id': order_id})
        order_row = result.fetchone()
        if not order_row:
            logger.warning(f"Order {order_id} not found in database")
            raise ValueError(f"Order {order_id} not found")
        if order_row.status not in ReturnsValidator.allowed_order_statuses:
            current_name = OrderStatus.get_customer_status_name(order_row.status)
            allowed_names = [OrderStatus.get_customer_status_name(s) for s in ReturnsValidator.allowed_order_statuses]
            logger.warning(f"Order {order_id} cannot be returned. Current status: {current_name} is not allowed. Allowed status(es): {', '.join(allowed_names)}")
            raise ValueError(
                f"Order {order_id} cannot be returned. "
                f"Current status: {current_name} is not allowed. "
                f"Allowed status(es): {', '.join(allowed_names)}"
            )
        return order_row, order_row.facility_name

    @staticmethod
    def validate_items_exist_and_quantities(current_items: Dict[str, object], items_to_return: List[Dict], already_returned: Dict[str, int]) -> List[object]:
        """Validate requested items exist and quantities do not exceed remaining quantities.

        Returns a list of matched item rows (from current_items) corresponding to items_to_return
        that passed existence and quantity checks. Aggregates and raises all errors at once.
        """
        errors: List[str] = []
        matched_rows: List[object] = []

        # Aggregate duplicate SKUs within the same request
        requested_by_sku: Dict[str, float] = {}
        for item in items_to_return:
            sku = item['sku']
            try:
                qty = float(item['quantity'])
            except (ValueError, TypeError):
                logger.error(f"Invalid quantity for SKU {sku}: {item.get('quantity')}")
                raise ValueError(f"Invalid quantity for SKU {sku}: {item.get('quantity')}")
            
            # Validate line_reference if provided
            line_reference = item.get('line_reference')
            if line_reference is not None:
                if sku not in current_items:
                    errors.append(f"Cannot validate line_reference for SKU {sku}: SKU not found in order")
                else:
                    current_row = current_items[sku]
                    # Verify line_reference matches the order item ID for this SKU
                    if hasattr(current_row, 'id') and current_row.id != line_reference:
                        errors.append(f"Invalid line_reference {line_reference} for SKU {sku}. Expected {current_row.id}")
            
            requested_by_sku[sku] = requested_by_sku.get(sku, 0.0) + qty

        for sku, qty in requested_by_sku.items():
            if sku not in current_items:
                errors.append(f"SKU {sku} not found in order")
                continue

            current_row = current_items[sku]
            # Compute effective available quantity for returns: prefer delivered, then fulfilled, then ordered quantity
            delivered_q = getattr(current_row, 'delivered_quantity', None)
            fulfilled_q = getattr(current_row, 'fulfilled_quantity', None)
            ordered_q = getattr(current_row, 'quantity', 0)
            # Safely convert to float while handling None
            try:
                delivered_val = float(delivered_q) if delivered_q is not None else 0.0
            except Exception:
                delivered_val = 0.0
            try:
                fulfilled_val = float(fulfilled_q) if fulfilled_q is not None else 0.0
            except Exception:
                fulfilled_val = 0.0
            try:
                ordered_val = float(ordered_q) if ordered_q is not None else 0.0
            except Exception:
                ordered_val = 0.0
            effective_available = delivered_val if delivered_val > 0 else (fulfilled_val if fulfilled_val > 0 else ordered_val)

            # Adjust with previously returned quantities for this order+sku
            prior_returned = 0.0
            if sku in already_returned:
                try:
                    prior_returned = float(already_returned.get(sku, 0))
                except (ValueError, TypeError):
                    prior_returned = 0.0

            remaining_qty = max(0.0, effective_available - prior_returned)

            # Special case: if only 1 unit was ordered/fulfilled and already one return exists
            if ordered_val == 1.0 and prior_returned >= 1.0:
                errors.append(
                    f"Cannot create return for {sku}. Quantity 1 already has a return initiated."
                )
                continue

            if qty <= 0:
                errors.append(f"Invalid return quantity {qty} for SKU {sku}")
                continue

            if qty > remaining_qty:
                errors.append(
                    f"Cannot return {int(qty)} units of {sku}. Only {int(remaining_qty)} unit(s) remaining to return"
                )
                continue

            matched_rows.append(current_row)

        if errors:
            logger.error(f"Item validation failed: {'; '.join(errors)}")
            raise ValueError(f"Item validation failed: {'; '.join(errors)}")
        return matched_rows

    @staticmethod
    def validate_item_eligibility(item_row, sku: str) -> List[str]:
        errors = []
        if not item_row.is_returnable:
            errors.append(f"{sku} is not eligible for return")
        if item_row.return_type not in ['10', '11']:
            errors.append(f"SKU {sku} return type '{item_row.return_type}' does not allow returns (must be '10' or '11')")
        # Items eligible for return only after delivery
        allowed_item_statuses = [OrderStatus.TMS_DELIVERED, OrderStatus.TMS_PARTIAL_DELIVERED]
        if item_row.status not in allowed_item_statuses:
            current_name = OrderStatus.get_customer_status_name(item_row.status)
            allowed_names = [OrderStatus.get_customer_status_name(s) for s in allowed_item_statuses]
            errors.append(
                f"SKU {sku} status {current_name} does not allow returns "
                f"(must be in {', '.join(allowed_names)})"
            )
        return errors

    @staticmethod
    def validate_full_return_eligibility(all_items: List[object]) -> None:
        errors: List[str] = []
        for row in all_items:
            errors.extend(ReturnsValidator.validate_item_eligibility(row, row.sku))
        if errors:
            logger.error(f"Full order return not allowed: {'; '.join(errors)}")
            raise ValueError(f"Full order return not allowed: {'; '.join(errors)}")

    @staticmethod
    def validate_items_eligibility(matched_rows: List[object]) -> None:
        """Validate eligibility for a set of matched item rows (aggregates all errors)."""
        errors: List[str] = []
        for row in matched_rows:
            errors.extend(ReturnsValidator.validate_item_eligibility(row, row.sku))
        if errors:
            logger.error(f"Return not allowed: {'; '.join(errors)}")
            raise ValueError(f"Return not allowed: {'; '.join(errors)}")

    @staticmethod
    def validate_order_for_return(order_id: str, route_mode: str) -> None:
        """Validate order exists and mode matches route origin"""
        
        order_service = OrderQueryService()
        order = order_service.get_order_by_id(order_id)
        
        if not order:
            logger.error(f"Order {order_id} not found")
            raise ValueError("Order not found")

         # Check if customer is a guest
        if str(order.get('customer_id', '')).lower() == 'guest':
            logger.error(f"Return not allowed for guest user | order_id={order_id}")
            raise ValueError("Returns are not allowed for guest customers")
        
        # Check if user_type is distributor (case-insensitive)
        if str(order.get('user_type', '')).lower() == 'distributor':
            logger.warning(f"Return not allowed for distributor user_type | order_id={order_id}")
            raise ValueError("Returns are not allowed for distributors")
        
        order_mode = order['order_mode']
        if order_mode not in ['app', 'pos']:
            logger.error(f"Invalid order mode: {order_mode}")
            raise ValueError(f"Invalid order mode: {order_mode}")
        
        if order_mode != route_mode:
            logger.warning(f"Unable to process return for {order_mode} order")
            raise ValueError(f"Unable to process return for {order_mode} order")

