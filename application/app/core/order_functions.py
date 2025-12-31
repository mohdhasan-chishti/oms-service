from fastapi import Request, HTTPException, BackgroundTasks
from datetime import datetime
from collections import defaultdict
import json
from decimal import Decimal

from app.dto.orders import OrderCreate  # type: ignore
from app.core.payment_defaults import PaymentDefaults
from app.core.constants import OrderStatus
from app.services.order_service import OrderService
from app.services.order_query_service import OrderQueryService
from app.services.payment_service import PaymentService
from app.repository.orders import OrdersRepository
from app.validations.orders import OrderCreateValidator

# Import helper functions from modular structure
from app.core.orders_creation.validation import (
    validate_order_and_payment,
    validate_and_enrich_facility,
    validate_facility_stock
)
from app.core.orders_creation.utils import (
    group_items_by_facility,
    generate_parent_order_id
)
from app.core.orders_creation.promotions import validate_and_apply_promotion
from app.core.orders_creation.creation import create_order_for_facility
from app.core.orders_creation.payments import PaymentProcessor
from app.core.orders_creation.order_processor import process_payments_for_orders


# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

STOCK_CHECK_ENABLED = configs.STOCK_CHECK_ENABLED

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("app.core.order_functions")


async def create_order_core(order: OrderCreate, request: Request, background_tasks: BackgroundTasks, origin: str = "app", **kwargs):

    try:
        user_id = getattr(request.state, "user_id", None)
        logger.info("Create order requested by user_id=%s, origin=%s", user_id, origin)
        user_phone_number = getattr(request.state, "phone_number", None)

        # Perform order and payment validations
        validator = validate_order_and_payment(order, user_id, origin)

        # Guest customer handling for POS
        if origin == "pos" and not order.customer_id:
            order.customer_id = 'guest'

        # Group items by facility
        facility_groups = group_items_by_facility(order.items, order.facility_name)
        
        # Generate parent_order_id for ALL orders
        parent_order_id = generate_parent_order_id()
        
        is_multi_facility = len(facility_groups) > 1
        if is_multi_facility:
            logger.info(f"Multi-facility order | parent_order_id={parent_order_id} | facilities={list(facility_groups.keys())}")
        else:
            logger.info(f"Single-facility order | parent_order_id={parent_order_id} | facility={order.facility_name}")
        
        # Validate and enrich items for EACH facility
        enriched_facility_data = {}
        for facility_name, facility_items in facility_groups.items():
            enriched_items, enriched_total = await validate_and_enrich_facility(
                facility_items=facility_items,
                facility_name=facility_name,
                user_type=order.user_type,
                origin=origin,
                promotion_type=order.promotion_type
            )
            enriched_facility_data[facility_name] = {'items': enriched_items, 'total': enriched_total}
        marketplace = order.marketplace or "ROZANA"
        skip_stock_check = marketplace.upper() == "CAFE"
        # Stock validation for EACH facility (only for app origin)
        if origin == "app":
            validator.validate_user_id_customer_id()
            if STOCK_CHECK_ENABLED and not skip_stock_check:
                for facility_name, facility_data in enriched_facility_data.items():
                    validate_facility_stock(facility_data['items'], facility_name)

        # Calculate total cart amount across all facilities
        cart_total = sum(facility_data['total'] for facility_data in enriched_facility_data.values())

        # Add delivery and packaging charges to overall total
        total_delivery_charges = 0.0
        total_packaging_charges = 0.0
        if order.order_charges:
            for facility_name, charges in order.order_charges.items():
                total_delivery_charges += charges.get('delivery_charge', 0.0)
                total_packaging_charges += charges.get('packaging_charge', 0.0)

        order.total_amount = cart_total + Decimal(str(total_delivery_charges)) + Decimal(str(total_packaging_charges))

        # Validate payment matches final cart total
        payment_total = sum(Decimal(str(p.amount)) for p in order.payment)
        if abs(payment_total - Decimal(str(order.total_amount))) > Decimal('0.10'):
            raise HTTPException(status_code=400, detail=f"payment amount {payment_total} does not match with total cart amount {order.total_amount}")

        # Extract payment modes
        payment_modes = [payment.payment_mode for payment in order.payment]

        # Filter facility data for promotion validation
        promotion_facility = order.promotion_facility or order.facility_name
        promotion_facility_data = enriched_facility_data
        if promotion_facility in enriched_facility_data:
            promotion_facility_data = {promotion_facility: enriched_facility_data[promotion_facility]}

        # Validate and apply promotion (if any)
        promotion_result = await validate_and_apply_promotion(
            promotion_code=order.promotion_code,
            customer_id=order.customer_id,
            enriched_facility_data=promotion_facility_data,
            origin=origin,
            payment_modes=payment_modes,
            promotion_type=order.promotion_type,
            cart_total=cart_total
        )

        # Create orders for all facilities
        created_orders = []
        order_data_dict = order.model_dump()
        
        # Sort facilities by total amount (descending)
        sorted_facilities = sorted(enriched_facility_data.items(), key=lambda x: x[1]['total'], reverse=True)
        
        # Create order for each facility
        for facility_name, facility_data in sorted_facilities:
            # Apply promotion to specific facility if promotion_facility is provided, otherwise first order (highest total)
            if order.promotion_facility and order.promotion_facility == facility_name:
                facility_promotion = promotion_result
            elif not order.promotion_facility and not created_orders:
                facility_promotion = promotion_result
            else:
                facility_promotion = {}
            
            facility_delivery_charge = 0.0
            facility_packaging_charge = 0.0
            if order.order_charges and facility_name in order.order_charges:
                facility_delivery_charge = order.order_charges[facility_name].get('delivery_charge', 0.0)
                facility_packaging_charge = order.order_charges[facility_name].get('packaging_charge', 0.0)
            
            facility_total_with_charges = facility_data['total'] + Decimal(str(facility_delivery_charge)) + Decimal(str(facility_packaging_charge))
            
            created_order = await create_order_for_facility(
                order_data_dict=order_data_dict,
                facility_name=facility_name,
                facility_items=facility_data['items'],
                facility_total=facility_total_with_charges,
                parent_order_id=parent_order_id,
                promotion_result=facility_promotion,
                origin=origin,
                request=request,
                background_tasks=background_tasks,
                stock_check_enabled=STOCK_CHECK_ENABLED,
                delivery_charge=facility_delivery_charge,
                packaging_charge=facility_packaging_charge,
                **kwargs
            )
            created_orders.append(created_order)

        # Process payments for all orders using PaymentProcessor
        payment_processor = PaymentProcessor()
        all_payment_records, primary_payment_records = await payment_processor.handle_order_payments(
            order=order,
            created_orders=created_orders,
            user_phone_number=user_phone_number,
            parent_order_id=parent_order_id
        )

        # Process payments for all orders
        await process_payments_for_orders(
            created_orders=created_orders,
            all_payment_records=all_payment_records,
            customer_id=order.customer_id,
            background_tasks=background_tasks
        )

        # Build response
        primary_order_id = created_orders[0]['order_id']
        is_multi_facility = len(created_orders) > 1

        # Concatenate all order IDs with comma + space
        order_ids_list = []
        for created_order in created_orders:
            order_ids_list.append(created_order['order_id'])

        all_order_ids_str = ", ".join(order_ids_list)

        # Aggregate payment details by payment_mode
        aggregated_payments = aggregate_payment_details(all_payment_records)

        response = {
            "success": True,
            "message": f"Successfully created {len(created_orders)} orders" if is_multi_facility else "Order created successfully",
            "id": created_orders[0]['internal_order_id'],
            "order_id": all_order_ids_str,
            "parent_order_id": parent_order_id,
            "payment_order_details": aggregated_payments,
            "multi_order": is_multi_facility,
            "application_environment": configs.APPLICATION_ENVIRONMENT
        }

        if is_multi_facility:
            response["all_order_ids"] = [o['order_id'] for o in created_orders]
            response["facilities"] = [o['facility_name'] for o in created_orders]

        if promotion_result:
            response["applied_promotion"] = {
                "promotion_code": promotion_result["promotion_code"],
                "promotion_type": promotion_result["promotion_type"],
                "promotion_discount": float(promotion_result["promotion_discount"]),
                "order_id": primary_order_id
            }

        logger.info(f"Order creation completed | parent_order_id={parent_order_id} | orders={len(created_orders)}")
        return response
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        logger.error("Error creating order: %s", str(traceback.print_exc()))
        raise HTTPException(status_code=500, detail="Internal server error") from exc


def aggregate_payment_details(all_payment_records: list) -> list:
    """
    Aggregate payment records by payment_mode.
    Groups payments by payment_mode and sums amounts.
    Uses earliest created_at timestamp for each payment mode.

    Args:
        all_payment_records: List of payment records from all orders
        
    Returns:
        List of aggregated payment records grouped by payment_mode
    """
    # Group by payment_mode
    payment_groups = defaultdict(list)
    for payment_record in all_payment_records:
        payment_mode = payment_record.get("payment_mode", "").lower()
        payment_groups[payment_mode].append(payment_record)

    # Aggregate each group
    aggregated = []
    for payment_mode, records in payment_groups.items():
        # Sum amounts
        total_amount = sum(Decimal(str(r.get("amount", 0))) for r in records)
        total_amount_paise = sum(int(r.get("amount_paise", 0)) for r in records)
        total_database_amount = sum(Decimal(str(r.get("database_payment_amount", 0))) for r in records)

        # Get earliest created_at timestamp
        created_at_timestamps = [r.get("created_at") for r in records if r.get("created_at")]
        earliest_created_at = min(created_at_timestamps) if created_at_timestamps else None

        # Use first record as template
        first_record = records[0]
        aggregated_record = dict(first_record)

        # Override only the fields we need to aggregate
        aggregated_record["amount"] = float(total_amount)
        aggregated_record["amount_paise"] = total_amount_paise
        aggregated_record["database_payment_amount"] = str(total_database_amount)
        aggregated_record["created_at"] = earliest_created_at
        aggregated.append(aggregated_record)

    logger.info(f"Aggregated {len(all_payment_records)} payment records into {len(aggregated)} payment modes")
    return aggregated


def _format_legacy_date(date_str):
    if not date_str or date_str is None:
        return ""
    try:
        parsed_date = datetime.strptime(str(date_str), "%d-%m-%Y")
        return parsed_date.strftime("%Y-%m-%dT%H:%M:%S.%f")
    except (ValueError, TypeError):
        return ""


async def get_order_details_core(order_id: str, user_id: str = None):
    """Shared logic for fetching full order details."""
    try:
        service = OrderQueryService()
        order = service.get_order_by_id(order_id)
        if not order:
            repo = OrdersRepository()
            legacy_header = repo.get_legacy_order_by_code(order_id)
            if not legacy_header:
                raise HTTPException(status_code=404, detail="Order not found")
            legacy_items = repo.get_legacy_order_items_by_order_id(legacy_header.get("id"))
            items = []
            for it in legacy_items:
                qty = float(it.get("quantity", 0))
                thumb = it.get("thumbnail_url")
                if thumb and not str(thumb).lower().startswith("http"):
                    thumb = f"{configs.AWS_OLD_BASE_URL}{str(thumb).lstrip('/')}"
                items.append({
                    "id": None,
                    "order_id": legacy_header.get("id"),
                    "sku": it.get("child_sku"),
                    "name": it.get("name"),
                    "quantity": qty,
                    "pos_extra_quantity": 0.0,
                    "unit_price": it.get("unit_price", 0.0),
                    "sale_price": it.get("sale_price", 0.0),
                    "status": "delivered",
                    "created_at": legacy_header.get("created_at"),
                    "updated_at": legacy_header.get("updated_at"),
                    "cgst": 0.0,
                    "sgst": 0.0,
                    "igst": 0.0,
                    "cess": 0.0,
                    "is_returnable": False,
                    "return_type": "00",
                    "return_window": 0,
                    "fulfilled_quantity": qty,
                    "delivered_quantity": qty,
                    "unfulfilled_quantity": 0.0,
                    "thumbnail_url": thumb,
                    "hsn_code": ""  # Legacy orders don't have HSN code
                })
            shipping_address = legacy_header.get("shipping_address")
            address = None
            if shipping_address:
                try:
                    if isinstance(shipping_address, str):
                        address_data = json.loads(shipping_address)
                    else:
                        address_data = shipping_address
                    if isinstance(address_data, dict):
                        address = {
                            "full_name": address_data.get("name"),
                            "phone_number": f"+91{address_data.get('phone')}" if address_data.get('phone') else None,
                            "address_line1": address_data.get("address"),
                            "address_line2": "",
                            "city": address_data.get("city"),
                            "state": address_data.get("state"),
                            "postal_code": str(address_data.get("postal_code")) if address_data.get("postal_code") else None,
                            "country": address_data.get("country"),
                            "type_of_address": "delivery",
                            "longitude": address_data.get("longitude") or 0.0,
                            "latitude": address_data.get("latitude") or 0.0
                        }
                except (json.JSONDecodeError, TypeError):
                    address = None
            delivery_date = legacy_header.get("delivery_date")
            order = {
                "id": legacy_header.get("id"),
                "order_id": legacy_header.get("code"),
                "customer_id": user_id,
                "customer_name": legacy_header.get("customer_name"),
                "facility_id": str(legacy_header.get("facility_id")),
                "facility_name": legacy_header.get("facility_name"),
                "status": legacy_header.get("delivery_status"),
                "can_cancel": False,
                "total_amount": float(legacy_header.get("grand_total", 0)),
                "eta": _format_legacy_date(delivery_date),
                "order_mode": legacy_header.get("order_mode"),
                "created_at": legacy_header.get("created_at"),
                "updated_at": legacy_header.get("updated_at"),
                "delivery_charge": 0.0,
                "packaging_charge": 0.0,
                "address": address,
                "items": items,
                "payments": [],
                "invoices": [],
                "refunds": [],
                "returns": []
            }
        return order
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error getting order details %s: %s", order_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


async def get_all_orders_core(
    user_id: str, page_size: int, page: int, 
    sort_order: str, search: str = None, 
    exclude_status: str = None,
    current_order_limit: str = None, ph_number: str = None, user_type: str = None):
    """Shared logic for listing all orders for the authenticated user with optional search functionality."""
    try:
        service = OrderQueryService()
        # Validate page parameters
        validator = OrderCreateValidator(user_id=user_id)
        validator.validate_page_size(page_size, page)

        # Validate exclude_status if provided
        exclude_statuses =[]
        if exclude_status is not None:
            if exclude_status != "10":
                raise HTTPException(status_code=400, detail="exclude_status must be '10'")
            exclude_statuses.append(int(exclude_status))
            exclude_statuses.append(OrderStatus.DRAFT)

        result = service.get_all_orders(user_id, page_size, page, sort_order, search, exclude_statuses, current_order_limit, ph_number, user_type)
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        logger.warning("Validation error getting orders for user %s: %s", user_id, ve)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error getting all orders for user %s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

async def get_all_facility_orders_core(facility_name: str, page_size: int, page: int, sort_order: str, filters: dict = None):
    """Shared logic for listing all orders for a facility with optional search functionality."""
    try:
        service = OrderQueryService()
        # Validate page parameters
        validator = OrderCreateValidator()
        validator.validate_page_size(page_size, page)

        result = service.get_all_facility_orders(facility_name, page_size, page, sort_order, filters)
        return result
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error getting all orders for facility %s: %s", facility_name, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


async def get_order_by_id(order_id: str):
    """Get order details by order ID for payment operations."""
    try:
        service = OrderQueryService()
        result = service.get_order_by_id(order_id)
        
        if not result:
            repo = OrdersRepository()
            legacy_header = repo.get_legacy_order_by_code(order_id)
            if not legacy_header:
                return None
            legacy_items = repo.get_legacy_order_items_by_order_id(legacy_header.get("id"))
            items = []
            for it in legacy_items:
                qty = float(it.get("quantity", 0))
                thumb = it.get("thumbnail_url")
                if thumb and not str(thumb).lower().startswith("http"):
                    thumb = f"{configs.AWS_OLD_BASE_URL}{str(thumb).lstrip('/')}"
                items.append({
                    "id": None,
                    "order_id": legacy_header.get("id"),
                    "sku": it.get("child_sku"),
                    "name": it.get("name"),
                    "quantity": qty,
                    "pos_extra_quantity": 0.0,
                    "unit_price": it.get("unit_price", 0.0),
                    "sale_price": it.get("sale_price", 0.0),
                    "status": "delivered",
                    "created_at": legacy_header.get("created_at"),
                    "updated_at": legacy_header.get("updated_at"),
                    "cgst": 0.0,
                    "sgst": 0.0,
                    "igst": 0.0,
                    "cess": 0.0,
                    "is_returnable": False,
                    "return_type": "no return no exchange",
                    "return_window": 0,
                    "fulfilled_quantity": qty,
                    "delivered_quantity": qty,
                    "unfulfilled_quantity": 0.0,
                    "thumbnail_url": thumb,
                    "hsn_code": ""  # Legacy orders don't have HSN code
                })
            return {
                "id": legacy_header.get("id"),
                "order_id": legacy_header.get("code"),
                "customer_id": legacy_header.get("user_id"),
                "customer_name": legacy_header.get("customer_name"),
                "facility_id": legacy_header.get("facility_id"),
                "facility_name": legacy_header.get("facility_name"),
                "status": legacy_header.get("delivery_status"),
                "total_amount": float(legacy_header.get("grand_total", 0)),
                "eta": None,
                "order_mode": legacy_header.get("order_mode"),
                "created_at": legacy_header.get("created_at"),
                "updated_at": legacy_header.get("updated_at"),
                "delivery_charge": 0.0,
                "packaging_charge": 0.0,
                "address": None,
                "items": items,
                "payment": [],
                "invoices": [],
                "refunds": [],
                "returns": []
            }
            
        return result
        
    except Exception as e:
        logger.error(f"Error fetching order {order_id}: {e}")
        return None

async def create_payment_for_order(
    order_id: str,
    payment_id: str,
    payment_amount: float,
    payment_mode: str = "online"
):
    """Create a payment record for an order (payments table only)."""
    try:
        from decimal import Decimal
        
        # First, get the internal integer ID from the external string order_id
        order = await get_order_by_id(order_id)
        if not order:
            logger.error(f"Order not found for order_id: {order_id}")
            return {"success": False, "message": f"Order {order_id} not found"}
        
        internal_order_id = order.get("id")  # Get the internal integer ID
        
        payment_modes = [p.payment_mode.lower() for p in order.payment]
        
        payment_service = PaymentService()
        initial_status = PaymentDefaults.initial_status_for_mode(payment_mode)
        result = await payment_service.create_payment_record(
            order_id=internal_order_id,  # Use internal integer ID
            payment_id=payment_id,
            payment_amount=Decimal(str(payment_amount)),
            payment_mode=payment_mode,
            payment_status=initial_status,
            total_amount=Decimal(str(order.get("total_amount", 0)))  # Pass the total order amount
        )
        
        if result.get("success"):
            logger.info(f"Created payment record for order {order_id}, payment {payment_id}")
        else:
            logger.error(f"Failed to create payment record for order {order_id}: {result.get('message')}")
            
        return result
        
    except Exception as e:
        logger.error(f"Error creating payment for order {order_id}: {e}")
        return {"success": False, "message": str(e)}


async def get_payment_status_for_order(order_id: str):
    """Get payment status summary for an order (from payments table only)."""
    try:
        # First, get the internal integer ID from the external string order_id
        order = await get_order_by_id(order_id)
        if not order:
            logger.error(f"Order not found for order_id: {order_id}")
            return {"success": False, "message": f"Order {order_id} not found"}

        internal_order_id = order.get("id")  # Get the internal integer ID

        payment_service = PaymentService()
        result = await payment_service.get_payment_status_for_order(internal_order_id)

        logger.info(f"Retrieved payment status for order {order_id}")
        return result

    except Exception as e:
        logger.error(f"Error getting payment status for order {order_id}: {e}")
        return {
            "order_id": order_id,
            "has_payments": False,
            "payment_status": None,
            "total_paid": 0.0,
            "payment_count": 0,
            "error": str(e)
        }


async def update_existing_payment(
    order_id: str,
    razorpay_payment_id: str,
    payment_amount: float,
    payment_status: int
):
    """Update existing pending payment record with Razorpay details instead of creating duplicate."""
    try:
        # Get the internal integer ID from the external string order_id
        order = await get_order_by_id(order_id)
        if not order:
            logger.error(f"Order not found for order_id: {order_id}")
            return {"success": False, "message": f"Order {order_id} not found"}

        internal_order_id = order.get("id")

        # Create a new PaymentService instance for this request
        payment_service = PaymentService()

        # Find the existing pending payment record for this order
        result = await payment_service.update_pending_payment_with_razorpay_details(
            order_id=internal_order_id,
            razorpay_payment_id=razorpay_payment_id,
            payment_amount=payment_amount,
            payment_status=payment_status
        )

        if result.get("success"):
            logger.info(f"Updated existing payment record for order {order_id} with Razorpay payment {razorpay_payment_id}")
        else:
            logger.error(f"Failed to update existing payment record for order {order_id}: {result.get('message')}")

        return result

    except Exception as e:
        logger.error(f"Error updating existing payment for order {order_id}: {e}")
        return {"success": False, "message": str(e)}