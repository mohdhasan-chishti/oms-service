from typing import Dict, Optional, List, Tuple
from fastapi import HTTPException
from app.core.constants import OrderStatus, PaymentStatus, RefundStatus, ReturnTypeConstants
from app.utils.order_utils import can_cancel_order
from app.connections.database import execute_raw_sql_readonly
from app.validations.orders import OrderCreateValidator
from app.services.legacy_orders import LegacyOrderService
from app.services.oms_orders import OMSOrderService
from app.utils.datetime_helpers import format_datetime_ist

# Request context
from app.middlewares.request_context import request_context

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

from app.config.settings import OMSConfigs
configs = OMSConfigs()

class OrderQueryService:
    """Service for handling order queries (Read operations) using SQLAlchemy raw SQL"""

    def __init__(self, db_conn=None):
        # Set module name for contextual logging
        request_context.module_name = 'order_query_service'

    def _get_return_type_description(self, return_type_code: str) -> str:
        """Convert return_type code to description using constants"""
        return ReturnTypeConstants.get_description(return_type_code)

    def get_order_by_id(self, order_id: str) -> Optional[Dict]:
        """Get single order by order_id from database with complete details"""
        
        try:
            sql = """
                SELECT o.id, o.order_id, o.customer_id, o.customer_name,
                       o.facility_id, o.facility_name,
                       o.status, o.total_amount, o.eta, o.order_mode, o.user_type,
                       o.created_at, o.updated_at, o.delivery_charge, o.packaging_charge,
                       oi.id as item_id, oi.sku, oi.typesense_id, oi.name, oi.quantity, oi.pos_extra_quantity, oi.unit_price, oi.sale_price,
                       oi.status AS item_status, oi.cgst, oi.sgst, oi.igst, oi.cess, 
                       oi.is_returnable, oi.return_type, oi.return_window, oi.created_at as item_created_at, 
                       oi.updated_at as item_updated_at, oi.fulfilled_quantity, oi.delivered_quantity,
                       oi.cancelled_quantity, oi.unfulfilled_quantity, oi.hsn_code,
                       oa.full_name, oa.phone_number, oa.address_line1, oa.address_line2,
                       oa.city, oa.state, oa.postal_code, oa.country, oa.type_of_address,
                       oa.longitude, oa.latitude, oi.thumbnail_url
                FROM orders o
                LEFT JOIN order_items oi ON oi.order_id = o.id
                LEFT JOIN order_addresses oa ON oa.order_id = o.id
                WHERE o.order_id = :order_id
            """
            
            rows = execute_raw_sql_readonly(sql, {'order_id': order_id})
            if not rows:
                return None

            header = rows[0]
            address = None
            items = []

            for record in rows:
                if address is None and record.get("full_name"):
                    address = {
                        "full_name": record.get("full_name"),
                        "phone_number": record.get("phone_number"),
                        "address_line1": record.get("address_line1"),
                        "address_line2": record.get("address_line2"),
                        "city": record.get("city"),
                        "state": record.get("state"),
                        "postal_code": record.get("postal_code"),
                        "country": record.get("country"),
                        "type_of_address": record.get("type_of_address"),
                        "longitude": float(record.get("longitude")) if record.get("longitude") is not None else None,
                        "latitude": float(record.get("latitude")) if record.get("latitude") is not None else None
                    }

                if record.get("sku"):
                    # Get return type interpretation
                    return_type_code = record.get("return_type", "00")
                    return_type_description = self._get_return_type_description(return_type_code)
                    if record.get("item_status") == OrderStatus.WMS_CANCELED:
                        unfulfilled_quantity = float(record.get("cancelled_quantity", 0))
                    else:
                        unfulfilled_quantity = float(record.get("unfulfilled_quantity", 0))

                    items.append({
                        "id": record.get("item_id"),
                        "order_id": header.get("id"),
                        "sku": record.get("sku"),
                        "typesense_id": record.get("typesense_id"),  # Add typesense_id
                        "name": record.get("name"),
                        "quantity": record.get("quantity"),
                        "pos_extra_quantity": float(record.get("pos_extra_quantity", 0)),
                        "unit_price": float(record.get("unit_price", 0)),
                        "sale_price": float(record.get("sale_price", 0)),
                        "status": OrderStatus.get_customer_status_name(record.get("item_status")),
                        "created_at": format_datetime_ist(record.get("item_created_at")),
                        "updated_at": format_datetime_ist(record.get("item_updated_at")),
                        "cgst": float(record.get("cgst", 0)),
                        "sgst": float(record.get("sgst", 0)),
                        "igst": float(record.get("igst", 0)),
                        "cess": float(record.get("cess", 0)),
                        "is_returnable": record.get("is_returnable", True),
                        "return_type": return_type_description,
                        "return_window": record.get("return_window", 7),
                        "fulfilled_quantity": float(record.get("fulfilled_quantity", 0)),
                        "delivered_quantity": float(record.get("delivered_quantity", 0)),
                        "unfulfilled_quantity": unfulfilled_quantity,
                        "thumbnail_url": record.get("thumbnail_url"),
                        "hsn_code": record.get("hsn_code", "")  # HSN code from database
                    })

            # Get payment details
            payment_sql = """
                SELECT pd.id as payment_pk, pd.payment_id, pd.payment_amount, pd.payment_mode, pd.payment_status,
                       pd.payment_order_id, pd.terminal_id
                FROM payment_details pd
                JOIN orders o ON o.id = pd.order_id
                WHERE o.order_id = :order_id
                ORDER BY pd.created_at DESC
                LIMIT 4
            """

            payment_rows = execute_raw_sql_readonly(payment_sql, {"order_id": order_id})

            # Get invoice details
            invoice_sql = """
                SELECT id.raven_link, id.invoice_s3_url
                FROM invoice_details id
                JOIN orders o ON o.id = id.order_id
                WHERE o.order_id = :order_id
                ORDER BY id.created_at DESC
            """

            invoice_rows = execute_raw_sql_readonly(invoice_sql, {"order_id": order_id})
            invoices = []
            for invoice_row in invoice_rows:
                invoice_url = invoice_row.get("invoice_s3_url") if invoice_row.get("invoice_s3_url") else ""
                raven_link = invoice_row.get("raven_link") if invoice_row.get("raven_link") else ""
                invoices.append({
                    "raven_link": raven_link,
                    "invoice_s3_url": invoice_url
                })

            # Get refunds for payments
            refund_sql = """
                SELECT rd.payment_id as payment_pk, rd.refund_id, rd.refund_amount, rd.refund_currency,
                       rd.refund_status, rd.refund_date, pd.payment_id
                FROM refund_details rd
                JOIN payment_details pd ON rd.payment_id = pd.id
                JOIN orders o ON o.id = pd.order_id
                WHERE o.order_id = :order_id
                and rd.refund_id not like '%cod_amount_unfulfilled_%'
                ORDER BY rd.created_at DESC
            """

            refund_rows = execute_raw_sql_readonly(refund_sql, {"order_id": order_id})
            
            # Create top-level refunds array
            refunds = []
            for refund_row in refund_rows:
                refund_data = {
                    "refund_id": refund_row.get("refund_id"),
                    "payment_id": refund_row.get("payment_id"),
                    "refund_amount": float(refund_row.get("refund_amount", 0)),
                    "refund_currency": refund_row.get("refund_currency"),
                    "refund_status": RefundStatus.get_description(refund_row.get("refund_status")),
                    "refund_date": format_datetime_ist(refund_row.get("refund_date"))
                }
                refunds.append(refund_data)

            # Create payments without nested refunds
            payments = []
            for payment_row in payment_rows:
                payments.append({
                    "payment_id": payment_row.get("payment_id"),
                    "payment_amount": float(payment_row.get("payment_amount", 0)),
                    "payment_mode": payment_row.get("payment_mode"),
                    "payment_status": PaymentStatus.get_description(payment_row.get("payment_status")),
                    "payment_order_id": payment_row.get("payment_order_id"),
                    "terminal_id": payment_row.get("terminal_id")
                })

            # Get returns
            returns_sql = """
                SELECT r.return_reference, r.return_type, r.return_reason, r.comments, r.status,
                       r.total_refund_amount, r.refund_status, r.created_at, r.updated_at,
                       ri.sku, ri.quantity_returned, ri.refund_amount
                FROM returns r
                LEFT JOIN return_items ri ON ri.return_id = r.id
                JOIN orders o ON o.id = r.order_id
                WHERE o.order_id = :order_id
                ORDER BY r.created_at DESC, ri.id
            """

            returns_rows = execute_raw_sql_readonly(returns_sql, {"order_id": order_id})
            returns = []
            for row in returns_rows:
                ref = row.get("return_reference")
                existing = next((r for r in returns if r["return_reference"] == ref), None)
                if not existing:
                    existing = {
                        "return_reference": ref,
                        "return_type": row.get("return_type"),
                        "return_reason": row.get("return_reason"),
                        "comments": row.get("comments"),
                        "status": row.get("status"),
                        "total_refund_amount": float(row.get("total_refund_amount", 0)),
                        "refund_status": row.get("refund_status"),
                        "created_at": format_datetime_ist(row.get("created_at")),
                        "updated_at": format_datetime_ist(row.get("updated_at")),
                        "items": []
                    }
                    returns.append(existing)
                if row.get("sku"):
                    existing["items"].append({
                        "sku": row.get("sku"),
                        "quantity_returned": row.get("quantity_returned"),
                        "refund_amount": float(row.get("refund_amount", 0))
                    })

            return {
                "id": header.get("id"),
                "order_id": header.get("order_id"),
                "customer_id": header.get("customer_id"),
                "customer_name": header.get("customer_name"),
                "facility_id": header.get("facility_id"),
                "facility_name": header.get("facility_name"),
                "status": OrderStatus.get_customer_status_name(header.get("status")),
                "can_cancel": can_cancel_order(header.get("status")),
                "total_amount": float(header.get("total_amount", 0)),
                "eta": format_datetime_ist(header.get("eta")),
                "order_mode": header.get("order_mode"),
                "user_type": header.get("user_type"),
                "created_at": format_datetime_ist(header.get("created_at")),
                "updated_at": format_datetime_ist(header.get("updated_at")),
                "delivery_charge": float(header.get("delivery_charge", 0)),
                "packaging_charge": float(header.get("packaging_charge", 0)),
                "address": address,
                "items": items,
                "payments": payments,
                "refunds": refunds,
                "invoices": invoices,
                "returns": returns
            }

        except Exception as e:
            logger.error(f"order_fetch_error | order_id={order_id} error={e}", exc_info=True)
            raise


    def get_clauses(self, search: str, exclude_statuses: str, sort_order: str = "desc", user_type: str = None) -> Tuple:
        # Prepare search clause and parameters
        search_clause = ""
        search_params = {}
        if search and search.strip():
            search_clause = " AND LOWER(o.order_id) LIKE LOWER(:search_term)"
            search_params['search_term'] = "%" + search.strip() + "%"

        # Prepare exclude clause and parameters
        exclude_clause = ""
        exclude_params = {}
        if exclude_statuses and len(exclude_statuses) > 0:
            exclude_clause = " AND o.status != ALL(:exclude_statuses)"                
            exclude_params['exclude_statuses'] = exclude_statuses
        
        # Prepare usertype clause and parameters
        usertype_clause = ""
        usertype_params = {}
        if user_type and user_type.strip():
            usertype_clause = " AND LOWER(o.user_type) = LOWER(:user_type)"
            usertype_params['user_type'] = user_type.strip()
        
        # Prepare order clause
        order_clause = "ORDER BY o.created_at DESC" if sort_order.lower() == "desc" else "ORDER BY o.created_at ASC"

        clauses = (search_clause, exclude_clause, usertype_clause, order_clause)
        params = (search_params, exclude_params, usertype_params)
        return clauses, params


    def get_all_orders(self, user_id: str, page_size: int = 20, page: int = 1, sort_order: str = "desc", search: str = None, exclude_statuses: str = None, current_order_limit: str = None, ph_number: str = None, user_type: str = None) -> Dict:
        """Get all orders for a user with pagination using SQLAlchemy raw SQL"""

        try:
            validator = OrderCreateValidator(user_id=user_id)

            clause, params = self.get_clauses(search, exclude_statuses, sort_order, user_type)
            oms_service = OMSOrderService()
            total_count_oms = oms_service.get_oms_orders_count(user_id, clause, params)
            
            current_order_limit = configs.CURRENT_ORDER_LIMIT
            
            # if total_count_oms < current_order_limit:
            #     print("fetching old orders")
            
            total_count_legacy = 0
            items_by_order = {}
            rows = []
            if total_count_oms >= current_order_limit:
                total_count = total_count_oms
                rows = oms_service.get_oms_orders(user_id, page_size, page, clause, params)
                order_ids = [row.get("id") for row in rows]
                if order_ids:
                    items_by_order = oms_service.get_oms_order_items_by_order_ids(order_ids)
            else:
                # Get OMS orders first, then fill remaining with legacy orders
                oms_rows = []
                oms_items_by_order = {}
                if total_count_oms > 0:
                    oms_rows = oms_service.get_oms_orders(user_id, page_size, page, clause, params)
                    oms_order_ids = [row.get("id") for row in oms_rows]
                    if oms_order_ids:
                        oms_items_by_order = oms_service.get_oms_order_items_by_order_ids(oms_order_ids)

                remaining_slots = page_size - len(oms_rows)
                legacy_rows = []
                legacy_items_by_order = {}
                total_count_legacy = 0
                if ph_number and str(ph_number).strip():
                    legacy_service = LegacyOrderService()
                    total_count_legacy = legacy_service.count_legacy_orders_by_phone(ph_number)
                    if remaining_slots > 0 and total_count_legacy > 0:
                        legacy_rows = legacy_service.get_legacy_orders_by_phone(ph_number, remaining_slots, page)
                        legacy_order_ids = [row.get("id") for row in legacy_rows]
                        if legacy_order_ids:
                            legacy_items_by_order = legacy_service.get_legacy_order_items_by_order_ids(legacy_order_ids)
                else:
                    logger.info(f"fetching legacy orders for user_id={user_id} page={page} size={page_size}")
                    legacy_rows, legacy_items_by_order, total_count_legacy = self.fetch_old_orders_for_user(None, remaining_slots, page, clause, params)

                base_url = getattr(configs, 'AWS_OLD_BASE_URL', '')
                if base_url and legacy_items_by_order:
                    for oid, items in legacy_items_by_order.items():
                        for item in items:
                            tu = item.get('thumbnail_url')
                            if tu and not str(tu).lower().startswith('http'):
                                item['thumbnail_url'] = base_url.rstrip('/') + '/' + str(tu).lstrip('/')

                rows = oms_rows + legacy_rows
                items_by_order = {**oms_items_by_order, **legacy_items_by_order}
                total_count = total_count_oms + total_count_legacy
                logger.info(f"total_count for user_id={user_id}={total_count}")

            # Validate page bounds with total count
            total_pages = validator.validate_pagination_params(page_size, page, total_count)
            
            if total_count == 0:
                return {
                    "orders": [],
                    "pagination": {
                        "current_page": page,
                        "page_size": page_size,
                        "total_count": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_previous": False
                    }
                }

            orders = []
            for row in rows:
                order_id = row.get("id")
                promotion_type = row.get('promotion_type', '')
                if promotion_type == 'cashback':
                    total_amount = float(row.get("total_amount", 0))
                else:
                    total_amount = float(row.get("total_amount", 0) - row.get('promotion_discount', 0))
                longitude = row.get("longitude")
                latitude = row.get("latitude")
                
                orders.append({
                    "id": order_id,
                    "order_id": row.get("order_id"),
                    "customer_id": row.get("customer_id"),
                    "customer_name": row.get("customer_name"),
                    "facility_id": row.get("facility_id"),
                    "facility_name": row.get("facility_name"),
                    "status": OrderStatus.get_customer_status_name(row.get("status")),
                    "total_amount": total_amount,
                    "eta": format_datetime_ist(row.get("eta")),
                    "created_at": format_datetime_ist(row.get("created_at")),
                    "updated_at": format_datetime_ist(row.get("updated_at")),
                    "longitude": float(longitude) if longitude is not None and longitude != '' else 0.0,
                    "latitude": float(latitude) if latitude is not None and latitude != '' else 0.0,
                    "order_mode": row.get("order_mode"),
                    "user_type": row.get("user_type"),
                    "history_items": items_by_order.get(order_id, [])
                })

            return {
                "orders": orders,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1
                }
            }

        except ValueError as ve:
            logger.warning(f"Validation error for user {user_id}: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"orders_fetch_error | user_id={user_id} error={e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch orders")

    def fetch_old_orders_for_user(self, legacy_user_id: Optional[int], limit: int, page: int, clause: Tuple, params: Tuple):
        if limit <= 0 or not legacy_user_id:
            return [], {}, 0
        legacy_service = LegacyOrderService()
        total_count_legacy = legacy_service.count_legacy_orders(legacy_user_id, clause, params)
        legacy_rows: List[Dict] = []
        legacy_items_by_order: Dict = {}
        if total_count_legacy > 0:
            legacy_rows = legacy_service.get_legacy_orders(legacy_user_id, limit, page, clause, params)
            legacy_order_ids = [row.get("id") for row in legacy_rows]
            if legacy_order_ids:
                legacy_items_by_order = legacy_service.get_legacy_order_items_by_order_ids(legacy_order_ids)
        logger.info(f"legacy_rows={legacy_rows}, legacy_items_by_order={legacy_items_by_order}, total_count_legacy={total_count_legacy}")
        return legacy_rows, legacy_items_by_order, total_count_legacy

    def get_order_again_products(self, user_id: str, page_size: int = 20, page: int = 1):
        try:
            # Validate pagination parameters
            validator = OrderCreateValidator(user_id=user_id)
            validator.validate_page_size(page_size, page)

            # First, get the total count
            count_sql = """
                SELECT COUNT(DISTINCT oi.sku) as total_count
                FROM orders o
                JOIN order_items oi 
                    ON oi.order_id = o.id
                WHERE o.customer_id = :user_id
            """

            count_rows = execute_raw_sql_readonly(count_sql, {"user_id": user_id})
            total_count = count_rows[0].get('total_count', 0) if count_rows else 0

            # Validate page bounds
            total_pages = validator.validate_pagination_params(page_size, page, total_count)

            # If no products, return empty result
            if total_count == 0:
                return {
                    "products": [],
                    "pagination": {
                        "current_page": page,
                        "page_size": page_size,
                        "total_count": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_previous": False
                    }
                }

            # Then get the paginated results
            recent_sql = """
                SELECT 
                    oi.sku,
                    COUNT(*) AS order_count
                FROM orders o
                JOIN order_items oi 
                    ON oi.order_id = o.id
                WHERE o.customer_id = :user_id
                GROUP BY oi.sku
                ORDER BY order_count DESC
                LIMIT :limit OFFSET :offset
            """

            rows = execute_raw_sql_readonly(
                recent_sql, 
                {"user_id": user_id, "limit": page_size, "offset": (page - 1) * page_size}
            )

            products = [row.get("sku") for row in rows if row.get("sku")]

            return {
                "products": products,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1
                }
            }

        except ValueError as ve:
            logger.warning(f"Validation error for user {user_id}: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(
                f"order_again_products_fetch_error | user_id={user_id} error={e}",
                exc_info=True,
            )
            return {"products": [], "pagination": {"current_page": page, "page_size": page_size, "total_count": 0, "total_pages": 0, "has_next": False, "has_previous": False}}


    def get_all_facility_orders(self, facility_name: str, page_size: int = 10, page: int = 1, sort_order: str = "desc", filters: dict = None) -> Dict:
        """Get all orders for a facility with pagination and optional search using SQLAlchemy raw SQL"""

        try:
            # Validate pagination parameters
            validator = OrderCreateValidator()
            validator.validate_page_size(page_size, page)

            # Dynamic filters system - configure allowed columns and their table aliases
            allowed_filters = {
                "order_id": "o.order_id",
                "customer_id": "o.customer_id",
                "customer_name": "o.customer_name", 
                "order_mode": "o.order_mode"
            }

            # Build dynamic filter clauses
            filter_clauses = []
            filter_params = {}

            if filters and isinstance(filters, dict):
                for filter_key, filter_value in filters.items():
                    if filter_key in allowed_filters and filter_value and str(filter_value).strip():
                        column_path = allowed_filters[filter_key]
                        param_name = f"filter_{filter_key}"
                        
                        if filter_key in ["customer_id"]:
                            filter_clauses.append(f" AND {column_path} = :{param_name}")
                            filter_params[param_name] = str(filter_value).strip()
                        elif filter_key in ["customer_name", "order_id", "order_mode"]:
                            # Partial match for these fields
                            filter_clauses.append(f" AND LOWER({column_path}) LIKE LOWER(:{param_name})")
                            filter_params[param_name] = f"%{str(filter_value).strip()}%"

            # Prepare order clause
            order_clause = "ORDER BY o.created_at DESC" if sort_order.lower() == "desc" else "ORDER BY o.created_at ASC"

            # First, get the total count
            count_sql = """
                SELECT COUNT(*) as total_count
                FROM orders o
                WHERE o.facility_name = :facility_name
            """
            for filter_clause in filter_clauses:
                count_sql += filter_clause

            count_params = {'facility_name': facility_name, **filter_params}
            count_rows = execute_raw_sql_readonly(count_sql, count_params)
            total_count = count_rows[0].get('total_count', 0) if count_rows else 0

            # Validate page bounds
            total_pages = validator.validate_pagination_params(page_size, page, total_count)

            # If no orders, return empty result
            if total_count == 0:
                return {
                    "orders": [],
                    "pagination": {
                        "current_page": page,
                        "page_size": page_size,
                        "total_count": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_previous": False
                    }
                }

            # Build main query with proper WHERE clause
            sql = """
                SELECT o.id, o.order_id, o.customer_id, o.customer_name,
                       o.facility_id, o.facility_name,
                       o.status, o.total_amount, o.eta,
                       o.created_at, o.updated_at, o.order_mode, o.promotion_discount, o.promotion_type
                FROM orders o
                WHERE o.facility_name = :facility_name
            """
            for filter_clause in filter_clauses:
                sql += filter_clause
            sql += " " + order_clause + " LIMIT :limit OFFSET :offset"

            sql_params = {
                'facility_name': facility_name,
                'limit': page_size,
                'offset': (page - 1) * page_size,
                **filter_params
            }
            
            rows = execute_raw_sql_readonly(sql, sql_params)

            orders = []
            for row in rows:
                order_id = row.get("id")
                promotion_type = row.get('promotion_type', '')
                if promotion_type == 'cashback':
                    total_amount = float(row.get("total_amount", 0))
                else:
                    total_amount = float(row.get("total_amount", 0) - row.get('promotion_discount', 0))
                
                orders.append({
                    "id": order_id,
                    "order_id": row.get("order_id"),
                    "customer_id": row.get("customer_id"),
                    "customer_name": row.get("customer_name"),
                    "facility_id": row.get("facility_id"),
                    "facility_name": row.get("facility_name"),
                    "status": OrderStatus.get_customer_status_name(row.get("status")),
                    "total_amount": total_amount,
                    "eta": format_datetime_ist(row.get("eta")),
                    "created_at": format_datetime_ist(row.get("created_at")),
                    "updated_at": format_datetime_ist(row.get("updated_at")),
                    "order_mode": row.get("order_mode")
                })

            return {
                "orders": orders,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1
                }
            }

        except ValueError as ve:
            logger.warning(f"Validation error for facility {facility_name}: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"facility_orders_fetch_error | facility_name={facility_name} error={e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch facility orders")

    def get_orders_by_customer_id(self, customer_id: str, page_size: int = 20, page: int = 1, sort_order: str = "desc", search: str = None) -> Dict:
        return self.get_all_orders(customer_id, page_size, page, sort_order, search)

    def get_order_items_by_customer_id(self, customer_id: str) -> List[Dict]:
        try:
            sql = """
                SELECT oi.id, oi.order_id, oi.sku, oi.name, oi.quantity, oi.pos_extra_quantity,
                       oi.unit_price, oi.sale_price, oi.status,
                       oi.cgst, oi.sgst, oi.igst, oi.cess, 
                       oi.is_returnable, oi.return_type, oi.return_window,
                       oi.created_at, oi.updated_at, oi.hsn_code
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE o.customer_id = :customer_id
                ORDER BY oi.created_at DESC
            """

            rows = execute_raw_sql_readonly(sql, {'customer_id': customer_id})

            items = []
            for row in rows:
                return_type_description = self._get_return_type_description(row.get("return_type", "00"))

                items.append({
                    "id": row.get("id"),
                    "order_id": row.get("order_id"),
                    "sku": row.get("sku"),
                    "name": row.get("name"),
                    "quantity": row.get("quantity"),
                    "pos_extra_quantity": float(row.get("pos_extra_quantity", 0)),
                    "unit_price": float(row.get("unit_price", 0)),
                    "sale_price": float(row.get("sale_price", 0)),
                    "status": OrderStatus.get_customer_status_name(row.get("status")),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "cgst": float(row.get("cgst", 0)),
                    "sgst": float(row.get("sgst", 0)),
                    "igst": float(row.get("igst", 0)),
                    "cess": float(row.get("cess", 0)),
                    "is_returnable": row.get("is_returnable", True),
                    "return_type": return_type_description,
                    "return_window": row.get("return_window", 7),
                    "hsn_code": row.get("hsn_code", "")  # HSN code from database
                })

            return items

        except Exception as e:
            logger.error(f"customer_order_items_fetch_error | customer_id={customer_id} error={e}", exc_info=True)
            raise

    def get_order_items_by_order_id(self, order_id: str) -> List[Dict]:
        try:
            sql = """
                SELECT oi.id, oi.order_id, oi.sku, oi.name, oi.quantity, oi.pos_extra_quantity,
                       oi.unit_price, oi.sale_price, oi.status,
                       oi.cgst, oi.sgst, oi.igst, oi.cess, 
                       oi.is_returnable, oi.return_type, oi.return_window,
                       oi.created_at, oi.updated_at, oi.hsn_code
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE o.order_id = :order_id
                ORDER BY oi.created_at DESC
            """

            rows = execute_raw_sql_readonly(sql, {'order_id': order_id})

            items = []
            for row in rows:
                return_type_description = self._get_return_type_description(row.get("return_type", "00"))

                items.append({
                    "id": row.get("id"),
                    "order_id": row.get("order_id"),
                    "sku": row.get("sku"),
                    "name": row.get("name"),
                    "quantity": row.get("quantity"),
                    "pos_extra_quantity": float(row.get("pos_extra_quantity", 0)),
                    "unit_price": float(row.get("unit_price", 0)),
                    "sale_price": float(row.get("sale_price", 0)),
                    "status": OrderStatus.get_customer_status_name(row.get("status")),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "cgst": float(row.get("cgst", 0)),
                    "sgst": float(row.get("sgst", 0)),
                    "igst": float(row.get("igst", 0)),
                    "cess": float(row.get("cess", 0)),
                    "is_returnable": row.get("is_returnable", True),
                    "return_type": return_type_description,
                    "return_window": row.get("return_window", 7),
                    "hsn_code": row.get("hsn_code", "")  # HSN code from database
                })

            return items

        except Exception as e:
            logger.error(f"order_items_fetch_error | order_id={order_id} error={e}", exc_info=True)
            raise