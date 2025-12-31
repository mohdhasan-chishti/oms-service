from typing import Dict, List
from app.connections.database import execute_raw_sql_readonly
from app.core.constants import RefundStatus

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

class RefundQueryService:
    def get_refunds_by_customer_id(self, customer_id: str) -> List[Dict]:
        try:
            logger.info(f"Getting refunds for customer_id: {customer_id}")
            sql = """
                SELECT o.order_id, p.payment_id, r.refund_id, r.refund_amount, r.refund_currency, r.refund_status, 
                       r.refund_date, r.speed_processed, r.receipt, r.batch_id, r.notes, r.created_at, r.updated_at
                FROM refund_details r
                JOIN payment_details p ON r.payment_id = p.id
                JOIN orders o ON p.order_id = o.id
                WHERE o.customer_id = :customer_id
                ORDER BY o.id DESC, p.id, r.created_at DESC
                LIMIT 4
            """

            rows = execute_raw_sql_readonly(sql, {'customer_id': customer_id})
            logger.info(f"Found {len(rows)} refund rows for customer_id: {customer_id}")

            # Group refunds by order_id and payment_id
            orders_dict = {}
            order_count = 0
            
            for row in rows:
                order_id = str(row.get("order_id"))
                payment_id = str(row.get("payment_id"))
                
                # Limit to 1 order_id
                if order_id not in orders_dict:
                    if order_count >= 1:
                        break
                    orders_dict[order_id] = {"order_id": order_id, "payments": {}}
                    order_count += 1
                
                # Initialize payment if not exists
                if payment_id not in orders_dict[order_id]["payments"]:
                    orders_dict[order_id]["payments"][payment_id] = {
                        "payment_id": payment_id,
                        "refunds": []
                    }
                
                # Add refund to payment
                refund_data = {
                    "refund_id": row.get("refund_id"),
                    "refund_amount": float(row.get("refund_amount", 0)),
                    "refund_currency": row.get("refund_currency"),
                    "refund_status": RefundStatus.get_description(row.get("refund_status")),
                    "refund_date": row.get("refund_date"),
                    "speed_processed": row.get("speed_processed"),
                    "receipt": row.get("receipt"),
                    "batch_id": row.get("batch_id"),
                    "notes": row.get("notes"),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at")
                }
                orders_dict[order_id]["payments"][payment_id]["refunds"].append(refund_data)

            # Convert to the desired format
            result = []
            for order_data in orders_dict.values():
                order_response = {
                    "order_id": order_data["order_id"],
                    "payments": list(order_data["payments"].values())
                }
                result.append(order_response)

            return result

        except Exception as e:
            logger.error(f"refund_fetch_error | customer_id={customer_id} error={e}", exc_info=True)
            raise