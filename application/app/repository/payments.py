"""
Payment repository for raw SQL operations
"""

from app.connections.database import get_raw_transaction, execute_raw_sql, execute_raw_sql_readonly
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from app.core.constants import PaymentStatus

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("app.payment_repository")

# Define IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


class PaymentRepository:
    """Repository for payment-related database operations using raw SQL"""

    def create_payment_record(
        self,
        order_id: int,
        payment_id: str,
        payment_amount: Decimal,
        payment_mode: str,
        payment_status: int = PaymentStatus.PENDING,
        total_amount: Optional[Decimal] = None,
        payment_order_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a payment record using raw SQL.
        Preserves Decimal precision for monetary values.
        """
        payment_date = datetime.now(IST)
        effective_total_amount = total_amount or payment_amount

        insert_query = text("""
            INSERT INTO payment_details (
                order_id, payment_id, payment_amount, payment_date, 
                payment_mode, payment_status, total_amount, payment_order_id,
                terminal_id, remarks, created_at, updated_at
            ) VALUES (
                :order_id, :payment_id, :payment_amount, :payment_date,
                :payment_mode, :payment_status, :total_amount, :payment_order_id,
                :terminal_id, :remarks, :created_at, :updated_at
            )
            RETURNING id, created_at, payment_amount
        """)

        try:
            with get_raw_transaction() as conn:
                result = conn.execute(insert_query, {
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "payment_amount": payment_amount,
                    "payment_date": payment_date,
                    "payment_mode": payment_mode,
                    "payment_status": payment_status,
                    "total_amount": effective_total_amount,
                    "payment_order_id": payment_order_id,
                    "terminal_id": terminal_id,
                    "remarks": remarks,
                    "created_at": payment_date,
                    "updated_at": payment_date,
                })

                # fetch result before commit
                row = result.fetchone()
                conn.commit()

                payment_record_id, created_at, database_payment_amount = row if row else (None, None, None)

            logger.info(
                f"payment_record_created | id={payment_record_id} "
                f"order_id={order_id} payment_id={payment_id} "
                f"mode={payment_mode} status={payment_status} "
                f"amount={payment_amount}"
                f"database_payment_amount={database_payment_amount}"
            )

            return {
                "success": True,
                "payment_record_id": payment_record_id,
                "payment_id": payment_id,
                "order_id": order_id,
                "payment_amount": payment_amount,
                "database_payment_amount": database_payment_amount,
                "payment_mode": payment_mode,
                "payment_status": payment_status,
                "created_at": created_at
            }

        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(
                f"payment_record_create_error | order_id={order_id} "
                f"payment_id={payment_id} mode={payment_mode} error={e}",
                exc_info=True,
            )
            raise e

    def get_payments_for_order(self, order_id: str) -> List[Dict[str, Any]]:
        """Get all payment records for an order"""
        try:
            query = """
                SELECT pd.id, pd.order_id, pd.payment_order_id, pd.payment_id, pd.payment_amount,
                       pd.payment_date, pd.payment_mode, pd.payment_status, pd.total_amount,
                       pd.terminal_id, pd.remarks, pd.created_at, pd.updated_at, orders.customer_id, orders.facility_name
                FROM payment_details as pd
                JOIN orders ON pd.order_id = orders.id
                WHERE orders.order_id = :order_id
                ORDER BY pd.created_at DESC
            """
            return execute_raw_sql(query, {"order_id": order_id})
        except Exception as e:
            logger.error(f"order_payments_fetch_error | order_id={order_id} error={e}", exc_info=True)
            raise e

    def upadate_the_razorpay_payment_id(self, id: int, razorpay_payment_id: str) -> Dict[str, Any]:
        """
        Update the razorpay_payment_id for a payment record
        """
        try:
            query = """
                UPDATE payment_details
                SET payment_id = :payment_id
                WHERE id = :id
            """
            execute_raw_sql(query, {"id": id, "payment_id": razorpay_payment_id}, fetch_results=False)
            return {"success": True}
        except Exception as e:
            logger.error(f"payment_record_update_error | payment_id={razorpay_payment_id} error={e}", exc_info=True)
            raise e

    def get_order_info_by_order_id(self, order_id: str) -> Optional[Dict]:
        """Get order information for webhook operations"""
        try:
            query = """
                SELECT facility_name, status, customer_id, total_amount
                FROM orders
                WHERE order_id = :order_id
            """
            rows = execute_raw_sql_readonly(query, {"order_id": order_id})
            if rows:
                return {
                    "facility_name": rows[0].get("facility_name"),
                    "status": rows[0].get("status"),
                    "customer_id": rows[0].get("customer_id"),
                    "total_amount": rows[0].get("total_amount")
                }
            return None
        except Exception as e:
            logger.error(f"get_order_info_error | order_id={order_id} error={e}", exc_info=True)
            return None

    def get_payment_by_id_and_order(self, payment_id: str, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get payment record by payment_id and order_id in a single query.
        Validates that both payment and order exist together.
        """
        try:
            query = """
                SELECT pd.id, pd.order_id, pd.payment_id, pd.payment_amount,
                       pd.payment_date, pd.payment_mode, pd.payment_status, pd.total_amount,
                       pd.created_at, pd.updated_at, o.order_id as order_reference_id
                FROM payment_details as pd
                JOIN orders as o ON pd.order_id = o.id
                WHERE pd.payment_id = :payment_id AND o.order_id = :order_id
                LIMIT 1
            """
            rows = execute_raw_sql_readonly(query, {"payment_id": payment_id, "order_id": order_id})
            if rows:
                return dict(rows[0])
            return None
        except Exception as e:
            logger.error(f"get_payment_by_id_and_order_error | payment_id={payment_id} order_id={order_id} error={e}", exc_info=True)
            return None

    def update_paytm_txn_id(self, payment_internal_id: int, paytm_txn_id: str) -> Dict[str, Any]:
        """
        Update the Paytm transaction ID (payment_id) for a payment record.
        Used to store the Paytm transaction ID returned from initiate_payment.
        """
        try:
            query = """
                UPDATE payment_details
                SET payment_id = :payment_id
                WHERE id = :id
            """
            execute_raw_sql(query, {"id": payment_internal_id, "payment_id": paytm_txn_id}, fetch_results=False)
            logger.info(f"paytm_txn_id_updated | payment_internal_id={payment_internal_id} paytm_txn_id={paytm_txn_id}")
            return {"success": True}
        except Exception as e:
            logger.error(f"update_paytm_txn_id_error | payment_internal_id={payment_internal_id} paytm_txn_id={paytm_txn_id} error={e}", exc_info=True)
            raise e

    def update_the_razorpay_order_id(self, id: int, razorpay_order_id: str) -> Dict[str, Any]:
        """
        Update the razorpay_order_id for a payment record
        """
        try:
            query = """
                UPDATE payment_details
                SET payment_order_id = :payment_order_id
                WHERE id = :id
            """
            execute_raw_sql(query, {"id": id, "payment_order_id": razorpay_order_id}, fetch_results=False)
            return {"success": True}
        except Exception as e:
            logger.error(f"payment_record_update_error | payment_order_id={razorpay_order_id} error={e}", exc_info=True)
            raise e

    def update_paytm_payment_details(self, payment_internal_id: int, terminal_id: str, payment_order_id: str) -> Dict[str, Any]:
        """
        Update terminal_id and payment_order_id for a Paytm payment record.
        Used when re-initiating Paytm POS payments.
        """
        try:
            query = """
                UPDATE payment_details
                SET terminal_id = :terminal_id, payment_order_id = :payment_order_id, updated_at = NOW()
                WHERE id = :id
            """
            execute_raw_sql(query, {
                "id": payment_internal_id,
                "terminal_id": terminal_id,
                "payment_order_id": payment_order_id
            }, fetch_results=False)
            logger.info(f"paytm_payment_details_updated | payment_id={payment_internal_id} terminal_id={terminal_id} payment_order_id={payment_order_id}")
            return {"success": True}
        except Exception as e:
            logger.error(f"update_paytm_payment_details_error | payment_id={payment_internal_id} error={e}", exc_info=True)
            raise e

    def get_active_payment_gateway_for_facility(self, facility_name: str) -> Optional[str]:
        """Get active payment gateway for a facility"""
        try:
            query = """
                SELECT payment_gateway
                FROM facility_payment_gateways
                WHERE facility_name = :facility_name AND is_active = true
                LIMIT 1
            """
            rows = execute_raw_sql_readonly(query, {"facility_name": facility_name})
            return rows[0].get("payment_gateway") if rows else None
        except Exception as e:
            logger.error(f"Error fetching payment gateway for facility {facility_name}: {e}")
            return None

    def get_orders_by_payment_order_id(self, payment_order_id: str) -> List[Dict]:
        """
        Get all orders by payment_order_id (gateway order ID like razorpay_order_id or cashfree_order_id).
        Used by webhooks to fetch all orders associated with a payment gateway order.
        For multi-facility orders, all orders share the same payment_order_id.
        """
        try:
            query = """
                SELECT DISTINCT o.order_id, o.facility_name, o.status, o.customer_id, o.total_amount
                FROM orders o
                JOIN payment_details pd ON o.id = pd.order_id
                WHERE pd.payment_order_id = :payment_order_id
                ORDER BY o.total_amount DESC
            """
            rows = execute_raw_sql_readonly(query, {"payment_order_id": payment_order_id})
            logger.info(f"fetched_orders_by_payment_order_id | payment_order_id={payment_order_id} count={len(rows)}")
            return rows
        except Exception as e:
            logger.error(f"get_orders_by_payment_order_id_error | payment_order_id={payment_order_id} error={e}", exc_info=True)
            return []
