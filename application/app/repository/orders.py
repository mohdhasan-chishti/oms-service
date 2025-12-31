from typing import Dict, List, Tuple, Optional, Union
from app.connections.database import execute_raw_sql_readonly, execute_raw_sql
from app.connections.mariadb_connection import mariadb_connection
from app.logging.utils import get_app_logger

logger = get_app_logger("app.orders_repository")


class OrdersRepository:
    def get_oms_orders_count(self, user_id: str, clause: Tuple = None, params: Tuple = None) -> int:
        try:
            search_clause, exclude_clause, user_type_clause, _ = clause
            search_params, exclude_params, user_type_params = params
            query = """
                SELECT COUNT(*) as total_count_oms
                FROM orders o
                WHERE o.customer_id = :user_id
            """
            if search_clause:
                query += search_clause
            if exclude_clause:
                query += exclude_clause
            if user_type_clause:
                query += user_type_clause
            rows = execute_raw_sql_readonly(query, {'user_id': user_id, **search_params, **exclude_params, **user_type_params})
            return rows[0].get('total_count_oms', 0) if rows else 0
        except Exception as e:
            logger.error(f"oms_orders_count_error | user_id={user_id} error={e}", exc_info=True)
            raise

    def get_oms_orders(self, user_id: str, page_size: int, page: int, clause: Tuple = None, params: Tuple = None) -> List[Dict]:
        try:
            search_clause, exclude_clause, user_type_clause, order_clause = clause
            search_params, exclude_params, user_type_params = params
            query = """
                SELECT o.id, o.order_id, o.customer_id, o.customer_name,
                       o.facility_id, o.facility_name,
                       o.status, o.total_amount, o.eta,
                       o.created_at, o.updated_at,
                       oa.longitude, oa.latitude, o.order_mode, o.promotion_discount, o.promotion_type, o.user_type
                FROM orders o
                LEFT JOIN LATERAL (
                    SELECT oa.longitude, oa.latitude
                    FROM order_addresses oa
                    WHERE oa.order_id = o.id
                    ORDER BY oa.id DESC LIMIT 1
                ) oa ON TRUE
                WHERE o.customer_id = :user_id
            """
            if search_clause:
                query += search_clause
            if exclude_clause:
                query += exclude_clause
            if user_type_clause:
                query += user_type_clause
            query += " " + order_clause + " LIMIT :limit OFFSET :offset"
            sql_params = {
                'user_id': user_id,
                'limit': page_size,
                'offset': (page - 1) * page_size,
                **search_params,
                **exclude_params,
                **user_type_params,
            }
            return execute_raw_sql_readonly(query, sql_params)
        except Exception as e:
            logger.error(f"oms_orders_fetch_error | user_id={user_id} page={page} size={page_size} error={e}", exc_info=True)
            raise

    def get_oms_order_items_by_order_ids(self, order_ids: List[str]) -> Dict:
        try:
            if not order_ids:
                return {}
            query = """
                SELECT oi.order_id, oi.sku, oi.thumbnail_url, oi.quantity, oi.name
                FROM order_items oi
                WHERE oi.order_id = ANY(:order_ids)
                ORDER BY oi.order_id, oi.id
            """
            rows = execute_raw_sql_readonly(query, {'order_ids': order_ids})
            items_by_order: Dict = {}
            for item_row in rows:
                oid = item_row.get("order_id")
                if oid not in items_by_order:
                    items_by_order[oid] = []
                items_by_order[oid].append({
                    "child_sku": item_row.get("sku"),
                    "thumbnail_url": item_row.get("thumbnail_url"),
                    "quantity": int(item_row.get("quantity", 0)) if item_row.get("quantity") is not None else 0,
                    "name": item_row.get("name") or "",
                })
            return items_by_order
        except Exception as e:
            logger.error(f"oms_order_items_fetch_error | order_ids_count={len(order_ids) if order_ids else 0} error={e}", exc_info=True)
            raise

    def count_legacy_orders(self, user_id: int) -> int:
        try:
            query = """
                SELECT COUNT(*) AS total_count FROM orders o
                WHERE o.user_id = %s
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (user_id,))
                    row = cursor.fetchone()
                    logger.info(f"legacy_orders_count={row}")
                    return int(row[0]) if row and row[0] is not None else 0
        except Exception as e:
            logger.error(f"legacy_orders_count_error | user_id={user_id} error={e}", exc_info=True)
            raise

    def count_legacy_orders_by_phone(self, phone_number: str) -> int:
        try:
            import re
            cleaned_phone = re.sub(r'[^\d]', '', phone_number)
            if cleaned_phone.startswith('91') and len(cleaned_phone) == 12:
                cleaned_phone = cleaned_phone[2:]
            elif len(cleaned_phone) == 10:
                pass
            else:
                cleaned_phone = cleaned_phone[-10:] if len(cleaned_phone) > 10 else cleaned_phone
            query = """
                SELECT COUNT(*) AS total_count FROM orders o
                LEFT JOIN users u ON u.id = o.user_id
                WHERE u.phone = %s
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (cleaned_phone,))
                    row = cursor.fetchone()
                    return int(row[0]) if row and row[0] is not None else 0
        except Exception as e:
            logger.error(f"legacy_orders_count_by_phone_error | phone_number={phone_number} error={e}", exc_info=True)
            return 0

    def get_legacy_orders(self, user_id: int, page_size: int, page: int) -> List[Dict]:
        try:
            offset = max((page - 1) * page_size, 0)
            query = """
                SELECT o.id, o.code, o.user_id, u.name AS customer_name,
                       o.sorting_hub_id AS facility_id, sh.stockone_code AS facility_name,
                       o.delivery_status, o.grand_total, '' AS eta,
                       o.created_at, o.updated_at, '' AS longitude,
                       '' AS latitude, o.platform
                FROM orders o
                LEFT JOIN users u ON u.id = o.user_id
                LEFT JOIN shorting_hubs sh ON sh.user_id = o.sorting_hub_id
                WHERE o.user_id = %s
                ORDER BY o.created_at DESC
                LIMIT %s OFFSET %s
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (user_id, page_size, offset))
                    rows = cursor.fetchall() or []
                    result = []
                    for r in rows:
                        result.append({
                            "id": str(r[0]) if r[0] is not None else None,
                            "order_id": r[1],
                            "customer_id": str(r[2]) if r[2] is not None else None,
                            "customer_name": r[3],
                            "facility_id": str(r[4]) if r[4] is not None else None,
                            "facility_name": r[5],
                            "status": r[6],
                            "total_amount": float(r[7]) if r[7] is not None else 0.0,
                            "eta": r[8],
                            "created_at": r[9],
                            "updated_at": r[10],
                            "longitude": r[11],
                            "latitude": r[12],
                            "order_mode": str(r[13]) if r[13] is not None else None,
                        })
                    logger.info(f"legacy_orders={result}")
                    return result
        except Exception as e:
            logger.error(f"legacy_orders_fetch_error | user_id={user_id} page={page} size={page_size} error={e}", exc_info=True)
            raise

    def get_legacy_orders_by_phone(self, phone_number: str, page_size: int, page: int) -> List[Dict]:
        try:
            import re
            cleaned_phone = re.sub(r'[^\d]', '', phone_number)
            if cleaned_phone.startswith('91') and len(cleaned_phone) == 12:
                cleaned_phone = cleaned_phone[2:]
            elif len(cleaned_phone) == 10:
                pass
            else:
                cleaned_phone = cleaned_phone[-10:] if len(cleaned_phone) > 10 else cleaned_phone
            offset = max((page - 1) * page_size, 0)
            query = """
                SELECT o.id, o.code, o.user_id, u.name AS customer_name,
                       o.sorting_hub_id AS facility_id, sh.stockone_code AS facility_name,
                       o.delivery_status, o.grand_total, '' AS eta,
                       o.created_at, o.updated_at, '' AS longitude,
                       '' AS latitude, o.platform
                FROM orders o
                LEFT JOIN users u ON u.id = o.user_id
                LEFT JOIN shorting_hubs sh ON sh.user_id = o.sorting_hub_id
                WHERE u.phone = %s
                ORDER BY o.created_at DESC
                LIMIT %s OFFSET %s
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (cleaned_phone, page_size, offset))
                    rows = cursor.fetchall() or []
                    result = []
                    for r in rows:
                        result.append({
                            "id": str(r[0]) if r[0] is not None else None,
                            "order_id": r[1],
                            "customer_id": str(r[2]) if r[2] is not None else None,
                            "customer_name": r[3],
                            "facility_id": str(r[4]) if r[4] is not None else None,
                            "facility_name": r[5],
                            "status": r[6],
                            "total_amount": float(r[7]) if r[7] is not None else 0.0,
                            "eta": r[8],
                            "created_at": r[9],
                            "updated_at": r[10],
                            "longitude": r[11],
                            "latitude": r[12],
                            "order_mode": str(r[13]) if r[13] is not None else None,
                        })
                    logger.info(f"legacy_orders_by_phone={result}")
                    return result
        except Exception:
            return []

    def get_legacy_order_by_code(self, order_code: str) -> Optional[Dict]:
        try:
            query = """
                SELECT o.id, o.code, o.user_id, u.name AS customer_name, o.delivery_date, o.shipping_address,
                       o.sorting_hub_id AS facility_id, sh.stockone_code AS facility_name,
                       o.delivery_status, o.grand_total, o.created_at, o.updated_at, o.platform AS order_mode
                FROM orders o
                LEFT JOIN users u ON u.id = o.user_id
                LEFT JOIN shorting_hubs sh ON sh.user_id = o.sorting_hub_id
                WHERE o.code = %s
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (order_code,))
                    row = cursor.fetchone()
                    if not row:
                        return None
                    columns = [col[0] for col in cursor.description]
                    result = dict(zip(columns, row))
                    return result
        except Exception as e:
            logger.error(f"legacy_order_by_code_fetch_error | order_code={order_code} error={e}", exc_info=True)
            return None

    def get_legacy_order_items_by_order_id(self, legacy_order_pk: Union[int, str]) -> List[Dict]:
        try:
            try:
                legacy_order_pk_int = int(legacy_order_pk)
            except (TypeError, ValueError):
                logger.error(
                    f"legacy_order_items_fetch_error | invalid_order_id={legacy_order_pk}",
                    exc_info=True,
                )
                return []
            query = """
                SELECT od.order_id, fp.child_sku, fp.thumbnail_image, od.quantity, od.variant_name, fp.name, fp.mrp, fp.ssp
                FROM order_details od
                LEFT JOIN orders o ON o.id = od.order_id
                LEFT JOIN final_products fp ON fp.product_id = od.product_id AND fp.sorting_hub_id = o.sorting_hub_id
                WHERE od.order_id = %s
                ORDER BY od.id
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (legacy_order_pk_int,))
                    rows = cursor.fetchall() or []
                    items: List[Dict] = []
                    for r in rows:
                        items.append({
                            "child_sku": r[1],
                            "thumbnail_url": r[2],
                            "quantity": int(r[3]) if r[3] is not None else 0,
                            "name": r[5] or r[4] or "",
                            "variant_name": r[4] or "",
                            "product_name": r[5] or "",
                            "unit_price": float(r[6]) if r[6] is not None else 0.0,
                            "sale_price": float(r[7]) if r[7] is not None else 0.0,
                        })
                    return items
        except Exception as e:
            logger.error(f"legacy_order_items_fetch_error | order_id={legacy_order_pk} error={e}", exc_info=True)
            return []

    def get_legacy_user_id_by_phone(self, phone_number: str):
        try:
            if phone_number.startswith('+91'):
                cleaned_phone = phone_number[3:]
            elif phone_number.startswith('91'):
                cleaned_phone = phone_number[2:]
            else:
                cleaned_phone = phone_number
            query = """
                SELECT id FROM users
                WHERE phone = %s LIMIT 1
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (cleaned_phone,))
                    row = cursor.fetchone()
                    return int(row[0]) if row and row[0] is not None else None
        except Exception as e:
            logger.error(f"legacy_user_lookup_error | phone={phone_number} error={e}", exc_info=True)
            raise

    def get_legacy_order_items_by_order_ids(self, order_ids: List[Union[int, str]]) -> Dict:
        try:
            if not order_ids:
                return {}
            numeric_ids = []
            for oid in order_ids:
                try:
                    numeric_ids.append(int(oid))
                except (TypeError, ValueError):
                    logger.warning(
                        f"legacy_order_items_fetch_warning | skipping_invalid_order_id={oid}"
                    )
            if not numeric_ids:
                return {}
            placeholders = ",".join(["%s"] * len(numeric_ids))
            query = f"""
                SELECT od.order_id, fp.child_sku, fp.thumbnail_image, od.quantity, od.variant_name
                FROM order_details od
                LEFT JOIN orders o ON o.id = od.order_id
                LEFT JOIN final_products fp ON fp.product_id = od.product_id AND fp.sorting_hub_id = o.sorting_hub_id
                WHERE od.order_id IN ({placeholders})
                ORDER BY od.order_id, od.id
            """
            with mariadb_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, numeric_ids)
                    rows = cursor.fetchall() or []
                    items_by_order: Dict[str, List[Dict]] = {}
                    for r in rows:
                        oid = str(r[0]) if r[0] is not None else None
                        if oid is None:
                            continue
                        if oid not in items_by_order:
                            items_by_order[oid] = []
                        items_by_order[oid].append({
                            "child_sku": r[1],
                            "thumbnail_url": r[2],
                            "quantity": int(r[3]) if r[3] is not None else 0,
                            "name": r[4] or "",
                        })
                    logger.info(f"legacy_order_items={items_by_order}")
                    return items_by_order
        except Exception as e:
            logger.error(f"legacy_order_items_fetch_error | order_ids_count={len(order_ids) if order_ids else 0} error={e}", exc_info=True)
            raise

    def update_parent_order_id(self, internal_order_id: int, parent_order_id: str):
        """Update parent_order_id for an order."""
        try:
            from app.connections.database import execute_raw_sql
            query = """
                UPDATE orders SET parent_order_id = :parent_order_id WHERE id = :internal_order_id
            """
            result = execute_raw_sql(query, {
                'parent_order_id': parent_order_id,
                'internal_order_id': internal_order_id
            }, fetch_results=False)
            logger.info(f"updated_parent_order_id | internal_order_id={internal_order_id} parent_order_id={parent_order_id}")
            return {"success": True}
        except Exception as e:
            logger.error(f"update_parent_order_id_error | internal_order_id={internal_order_id} parent_order_id={parent_order_id} error={e}", exc_info=True)
            raise

    def get_orders_by_parent_order_id(self, parent_order_id: str) -> List[Dict]:
        """Fetch all orders with the given parent_order_id."""
        try:
            query = """
                SELECT id, order_id, facility_name, status, total_amount
                FROM orders
                WHERE parent_order_id = :parent_order_id
                ORDER BY total_amount DESC
            """
            orders = execute_raw_sql_readonly(query, {'parent_order_id': parent_order_id})
            logger.info(f"fetched_orders_by_parent | parent_order_id={parent_order_id} count={len(orders)}")
            return orders
        except Exception as e:
            logger.error(f"get_orders_by_parent_order_id_error | parent_order_id={parent_order_id} error={e}", exc_info=True)
            raise

    def get_order_status_by_order_id(self, order_id: str) -> Optional[int]:
        """Get order status by order_id"""
        query = """ SELECT status FROM orders WHERE order_id = :order_id """
        result = execute_raw_sql(query, {'order_id': order_id})
        return result[0].get('status') if result else None

    def update_order_and_items_status_by_order_id(self, order_id: str, status: int):
        """Update order status by order_id"""
        query = """ UPDATE orders SET status = :status WHERE order_id = :order_id """
        execute_raw_sql(query, {'status': status, 'order_id': order_id}, fetch_results=False)

        query = """ SELECT id FROM orders WHERE order_id = :order_id """
        result = execute_raw_sql(query, {'order_id': order_id})
        order_pk = result[0].get('id') if result else None

        query = """ UPDATE order_items SET status = :status WHERE order_id = :order_pk """
        execute_raw_sql(query, {'status': status, 'order_pk': order_pk}, fetch_results=False)
