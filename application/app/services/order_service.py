from typing import Dict
import random
import string
from app.utils.order_utils import get_utc
from sqlalchemy import text
from app.core.constants import OrderStatus, SystemConstants
from app.connections.database import get_raw_transaction
from app.utils.datetime_helpers import format_datetime_ist
from app.dto.phone_validations import validate_phone_number
from fastapi import HTTPException

# Request context
from app.middlewares.request_context import request_context

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

from app.services.order_meta_service import OrderMetaService
from app.utils.firebase_utils import get_customer_id_from_phone_number

def generate_random_prefix() -> str:
    """Generate a random 4-character alphanumeric string for order ID prefix.

    Returns:
        str: A 4-character string containing uppercase letters and digits (e.g., 'A2K4', '489K', 'X7B9')
    """
    characters = string.ascii_uppercase + string.digits
    while True:
        prefix = ''.join(random.choices(characters, k=4))
        if not (prefix.upper().startswith(('ORD', 'POS', 'SAM', 'MN'))):
            return prefix


class OrderService:
    """Service for handling order commands (Create, Update, Cancel) using SQLAlchemy raw SQL"""

    def __init__(self):
        # Set module name for contextual logging
        request_context.module_name = 'order_service'

    async def get_initial_status(self, origin, payment_modes: list[str]):
        """Decide initial status based on origin and payment modes.
        If any online/razorpay is present → DRAFT, otherwise OPEN.
        """
        if (origin == "app" and any(pm in ["razorpay", "online", "cashfree"] for pm in payment_modes)) or (origin == "pos" and any(pm in ["paytm_pos"] for pm in payment_modes)):
            return OrderStatus.DRAFT

        return OrderStatus.OPEN

    async def create_order(self, order_data: Dict, origin: str = "app", **kwargs) -> Dict:
        """Create order - Direct write to database with auto-generated order_id using SQLAlchemy"""

        try:
            logger.info(f"order_create_initiated | customer_id={order_data.get('customer_id')} facility_id={order_data.get('facility_id')}")

            # Validation Layer
            required_fields = ['customer_id', 'facility_id', 'facility_name', 'total_amount']
            for field in required_fields:
                if field not in order_data or not order_data[field]:
                    logger.error(f"order_create_validation_error | missing_field={field}")
                    raise ValueError(f"Missing required field: {field}")
            
            customer_name = order_data.get("customer_name") or ""

            eta = get_utc(order_data.get("eta"))
            logger.info(f"eta_computed | eta={eta.isoformat()} eta_hours={SystemConstants.DEFAULT_ETA_HOURS}")

            # Payment Mode
            #payment_mode = order_data.get("payment_mode", "cod")
            #initial_status = await self.get_initial_status(origin, payment_mode)
            if "payment" in order_data and isinstance(order_data["payment"], list):
                payment_modes = [p.get("payment_mode", "cod").lower() for p in order_data["payment"]]
            else:
                payment_modes = [order_data.get("payment_mode", "cod").lower()]
            initial_status = await self.get_initial_status(origin, payment_modes)

            # Generate random prefix for order_id prefix
            random_prefix = generate_random_prefix()

            biller_id = kwargs.get("biller_id", "")
            biller_name = kwargs.get("biller_name", "")

            phone_number = order_data.get('address', {}).get('phone_number')
            if origin == "pos" and phone_number != '+911234567890':
                validated_phone = validate_phone_number(phone_number)
                customer_id = await get_customer_id_from_phone_number(validated_phone, origin=origin)
            else:
                customer_id = order_data['customer_id']

            # Promotion
            promotion_details = order_data.get("promotion_result", {})

            # Use SQLAlchemy transaction for atomic operation
            with get_raw_transaction() as conn:
                try:
                    # Insert order with SQLAlchemy raw SQL - omit timestamp columns to use database defaults
                    order_insert_sql = """
                        INSERT INTO orders (
                            random_prefix, customer_id, customer_name, 
                            facility_id, facility_name, status, total_amount, eta,
                            order_mode, is_approved, biller_id, biller_name, promotion_code, promotion_type, promotion_discount, user_type, marketplace, referral_id,
                            domain_name, provider_id, location_id, delivery_charge, packaging_charge
                        ) 
                        VALUES (
                            :random_prefix, :customer_id, :customer_name, 
                            :facility_id, :facility_name, :status, :total_amount, :eta,
                            :order_mode, :is_approved, :biller_id, :biller_name, :promotion_code, :promotion_type, :promotion_discount, :user_type, :marketplace, :referral_id,
                            :domain_name, :provider_id, :location_id, :delivery_charge, :packaging_charge
                        )
                        RETURNING id, order_id, created_at
                    """

                    # Extract domain_name, provider_id, location_id from items, finding first non-empty values
                    domain_name = provider_id = location_id = ''
                    for item in order_data['items']:
                        if item.get('domain_name'):
                            domain_name = item.get('domain_name', '')
                            provider_id = item.get('provider_id', '')
                            location_id = item.get('location_id', '')
                            break

                    total_amount = float(order_data.get('original_total_amount', 0.0)) + order_data.get('delivery_charge', 0.0) + order_data.get('packaging_charge', 0.0)

                    order_params = {
                        'random_prefix': random_prefix,
                        'customer_id': customer_id,
                        'customer_name': customer_name,
                        'facility_id': order_data['facility_id'],
                        'facility_name': order_data['facility_name'],
                        'status': initial_status,
                        'total_amount': total_amount,
                        'eta': eta,
                        'order_mode': origin,
                        'is_approved': order_data.get('is_approved', False),
                        'biller_id': biller_id,
                        'biller_name': biller_name,
                        'promotion_code': promotion_details.get('promotion_code', ''),
                        'promotion_type': promotion_details.get('promotion_type', ''),
                        'promotion_discount': promotion_details.get('promotion_discount', 0.0),
                        'user_type': order_data.get('user_type', 'customer'),
                        'marketplace': order_data.get('marketplace', 'ROZANA'),
                        'referral_id': order_data.get('referral_id', ''),
                        'domain_name': domain_name,
                        'provider_id': provider_id,
                        'location_id': location_id,
                        'delivery_charge': order_data.get('delivery_charge', 0.0),
                        'packaging_charge': order_data.get('packaging_charge', 0.0),
                    }

                    result = conn.execute(text(order_insert_sql), order_params)
                    order_row = result.fetchone()

                    if not order_row:
                        raise Exception("Failed to create order")

                    order_internal_id = order_row.id
                    generated_order_id = order_row.order_id
                    created_at = order_row.created_at

                    logger.info(f"order_row_created | id={order_internal_id} order_id={generated_order_id}")

                    # Insert order items with corrected foreign key reference (orders.id)
                    if 'items' in order_data and order_data['items']:
                        for item in order_data['items']:
                            item_insert_sql = """
                                INSERT INTO order_items (
                                    order_id, sku, typesense_id, name, quantity, pos_extra_quantity, unit_price, sale_price, original_sale_price, status,
                                    cgst, sgst, igst, cess, is_returnable, return_type, return_window, selling_price_net, wh_sku, pack_uom_quantity, thumbnail_url, hsn_code,
                                    category, sub_category, sub_sub_category, brand_name, marketplace, referral_id,
                                    domain_name, provider_id, location_id
                                ) VALUES (
                                    :order_id, :sku, :typesense_id, :name, :quantity, :pos_extra_quantity, :unit_price, :sale_price, :original_sale_price, :status,
                                    :cgst, :sgst, :igst, :cess, :is_returnable, :return_type, :return_window, :selling_price_net, :wh_sku, :pack_uom_quantity, :thumbnail_url, :hsn_code,
                                    :category, :sub_category, :sub_sub_category, :brand_name, :marketplace, :referral_id,
                                    :domain_name, :provider_id, :location_id
                                )
                            """

                            item_params = {
                                'order_id': order_internal_id,  # Use primary key, not order_id string
                                'sku': item['sku'],
                                'typesense_id': item.get('typesense_id') or '',  # Add typesense_id with empty string default
                                'name': item.get('name'),  # Optional name field
                                'quantity': item['quantity'],
                                'pos_extra_quantity': item.get('pos_extra_quantity', 0.0),
                                'unit_price': item['unit_price'],
                                'sale_price': item['sale_price'],
                                'original_sale_price': item.get('original_sale_price', item['sale_price']),  # Default to sale_price if not provided
                                'cgst': item.get('cgst', 0.0),
                                'sgst': item.get('sgst', 0.0),
                                'igst': item.get('igst', 0.0),
                                'cess': item.get('cess', 0.0),
                                'is_returnable': item.get('is_returnable', False),
                                'return_type': item.get('return_type', '00'),
                                'return_window': item.get('return_window', 0),
                                'selling_price_net': item.get('selling_price_net', 0.0),
                                'status': initial_status,
                                'wh_sku': item.get('wh_sku', ''),
                                'pack_uom_quantity': item.get('pack_uom_quantity', 1),
                                'thumbnail_url': item.get('thumbnail_url', None),
                                'hsn_code': item.get('hsn_code', ''),  # HSN code from Typesense
                                'category': item.get('category', ''),
                                'sub_category': item.get('sub_category', ''),
                                'sub_sub_category': item.get('sub_sub_category', ''),
                                'brand_name': item.get('brand_name', ''),
                                'marketplace': item.get('marketplace', 'ROZANA'),
                                'referral_id': item.get('referral_id', ''),
                                'domain_name': item.get('domain_name', ''),
                                'provider_id': item.get('provider_id', ''),
                                'location_id': item.get('location_id', ''),
                            }

                            conn.execute(text(item_insert_sql), item_params)

                    # Insert order address with corrected foreign key reference (orders.id)
                    if 'address' in order_data and order_data['address']:
                        address = order_data['address']
                        address_insert_sql = """
                            INSERT INTO order_addresses (
                                order_id, full_name, phone_number, address_line1, address_line2,
                                city, state, postal_code, country, type_of_address, longitude, latitude
                            ) VALUES (
                                :order_id, :full_name, :phone_number, :address_line1, :address_line2,
                                :city, :state, :postal_code, :country, :type_of_address, :longitude, :latitude
                            )
                        """

                        address_params = {
                            'order_id': order_internal_id,  # Use primary key, not order_id string
                            'full_name': address['full_name'],
                            'phone_number': address['phone_number'],
                            'address_line1': address['address_line1'],
                            'address_line2': address.get('address_line2'),
                            'city': address['city'],
                            'state': address['state'],
                            'postal_code': address['postal_code'],
                            'country': address['country'],
                            'type_of_address': address.get('type_of_address', 'delivery'),
                            'longitude': address.get('longitude'),
                            'latitude': address.get('latitude')
                        }
                        
                        conn.execute(text(address_insert_sql), address_params)

                    # Commit transaction
                    conn.commit()
                    logger.info(f"order_create_success | order_id={generated_order_id} id={order_internal_id}")

                    return {
                        "success": True,
                        "message": f"Order {generated_order_id} created successfully",
                        "order_id": generated_order_id,
                        "id": order_internal_id,  # ← Add this line!
                        "eta": format_datetime_ist(eta),
                        "created_at": created_at
                    }

                except Exception as db_error:
                    conn.rollback()
                    logger.error(f"order_create_db_error | error={db_error}", exc_info=True)
                    return {
                        "success": False,
                        "message": f"Database error: {str(db_error)}"
                    }

        except ValueError as validation_error:
            logger.warning(f"order_create_validation_error | error={validation_error}")
            return {
                "success": False,
                "message": f"Validation error: {str(validation_error)}"
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"order_create_unexpected_error | error={exc}", exc_info=True)
            return {
                "success": False,
                "message": f"Unexpected error: {str(exc)}"
            }

    async def update_order_status(self, order_id: str, status) -> Dict:
        """Update order status in both orders and order_items tables using SQLAlchemy"""

        try:
            with get_raw_transaction() as conn:
                # Update order status
                update_order_sql = """
                    UPDATE orders 
                    SET status = :status, updated_at = NOW() 
                    WHERE order_id = :order_id
                """

                # Handle both integer constants and string statuses
                if isinstance(status, int):
                    # If it's an integer constant, use it directly
                    status_value = status
                elif isinstance(status, str):
                    # If it's a string, look it up in the mapping
                    status_value = OrderStatus.DB_STATUS_MAP.get(status)
                    if status_value is None:
                        logger.error(
                            f"order_status_update_invalid_status | status={status}"
                        )
                        return {
                            "success": False,
                            "message": f"Unknown status: {status}"
                        }
                else:
                    logger.error(
                        f"order_status_update_invalid_type | status_type={type(status)}"
                    )
                    return {
                        "success": False,
                        "message": f"Invalid status type: {type(status)}"
                    }

                result = conn.execute(text(update_order_sql), {
                    'status': status_value,
                    'order_id': order_id
                })

                if result.rowcount == 0:
                    logger.warning(f"order_status_update_not_found | order_id={order_id}")
                    return {
                        "success": False,
                        "message": f"Order {order_id} not found"
                    }

                # Get the primary key for updating items
                get_order_id_sql = "SELECT id FROM orders WHERE order_id = :order_id"
                order_result = conn.execute(text(get_order_id_sql), {'order_id': order_id})
                order_row = order_result.fetchone()

                if order_row:
                    # Update all items status using primary key
                    update_items_sql = """
                        UPDATE order_items 
                        SET status = :status 
                        WHERE order_id = :order_pk
                    """

                    conn.execute(text(update_items_sql), {
                        'status': status,
                        'order_pk': order_row.id
                    })

                conn.commit()
                logger.info(f"order_status_updated | order_id={order_id} status={status}")

                return {
                    "success": True,
                    "message": f"Order {order_id} status updated to {status}"
                }

        except Exception as e:
            logger.error(f"order_status_update_error | order_id={order_id} error={e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to update order status: {str(e)}"
            }

    async def update_item_status(self, order_id: str, sku: str, status: str) -> Dict:
        """Update status of a specific item within an order using SQLAlchemy"""

        try:
            with get_raw_transaction() as conn:
                # Get order primary key
                get_order_sql = "SELECT id FROM orders WHERE order_id = :order_id"
                order_result = conn.execute(text(get_order_sql), {'order_id': order_id})
                order_row = order_result.fetchone()

                if not order_row:
                    logger.warning(f"order_item_status_update_order_not_found | order_id={order_id}")
                    return {
                        "success": False,
                        "message": "Order not found"
                    }

                order_pk = order_row.id

                # Check if item exists in the order (using primary key)
                check_item_sql = """
                    SELECT id FROM order_items
                    WHERE order_id = :order_pk AND sku = :sku
                """

                item_result = conn.execute(text(check_item_sql), {
                    'order_pk': order_pk,
                    'sku': sku
                })

                if not item_result.fetchone():
                    logger.warning(f"order_item_status_update_item_not_found | order_id={order_id} sku={sku}")
                    return {
                        "success": False,
                        "message": f"Item with SKU '{sku}' not found in order '{order_id}'"
                    }

                # Update specific item status
                update_item_sql = """
                    UPDATE order_items
                    SET status = :status, updated_at = NOW()
                    WHERE order_id = :order_pk AND sku = :sku
                """
                
                conn.execute(text(update_item_sql), {
                    'status': status,
                    'order_pk': order_pk,
                    'sku': sku
                })

                conn.commit()
                logger.info(f"order_item_status_updated | order_id={order_id} sku={sku} status={status}")
                return {
                    "success": True,
                    "message": f"Item '{sku}' status updated to '{status}'",
                    "order_id": order_id,
                    "sku": sku,
                    "status": status
                }
        except Exception as e:
            logger.error(f"order_item_status_update_error | order_id={order_id} sku={sku} error={e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to update item status: {str(e)}"
            }

    async def get_facility_name(self, order_id: str) -> Dict:
        try:
            with get_raw_transaction() as conn:
                get_facility_name_sql = "SELECT facility_name FROM orders WHERE order_id = :order_id"
                result = conn.execute(text(get_facility_name_sql), {'order_id': order_id})
                facility_name = result.fetchone()
                return facility_name
        except Exception as e:
            logger.error(f"order_facility_name_error | order_id={order_id} error={e}", exc_info=True)
            return None

    @staticmethod
    def get_return_eligible_items(order_id: str) -> list[Dict]:
        """Return items eligible for full return (status = TMS_DELIVERED) by customer order_id.

        Returns list of dicts: [{"sku": str, "quantity": Decimal}]
        """
        try:
            with get_raw_transaction() as conn:
                # Get internal PK for the order
                get_pk_sql = "SELECT id FROM orders WHERE order_id = :order_id"
                order_result = conn.execute(text(get_pk_sql), {'order_id': order_id})
                order_row = order_result.fetchone()
                if not order_row:
                    return []

                # Fetch delivered items
                get_items_sql = (
                    "SELECT sku, quantity, fulfilled_quantity FROM order_items "
                    "WHERE order_id = :order_pk AND status = :delivered"
                )
                items_result = conn.execute(
                    text(get_items_sql),
                    {
                        'order_pk': order_row.id,
                        'delivered': OrderStatus.TMS_DELIVERED,
                    },
                )
                rows = items_result.fetchall()
                return [{"sku": r.sku, "quantity": r.fulfilled_quantity} for r in rows]
        except Exception as e:
            logger.error(f"get_return_eligible_items_error | order_id={order_id} error={e}", exc_info=True)
            return []