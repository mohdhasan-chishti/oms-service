from typing import  Tuple
from app.connections.database import execute_raw_sql_readonly
from app.logging.utils import get_app_logger

logger = get_app_logger("app.orders_repository")


class InvoiceRepository:
    def get_invoices_by_order_id(self, order_id: str):
        try:
            sql = """SELECT inv.invoice_number, inv.invoice_s3_url, inv.raven_link
                FROM invoice_details inv
                JOIN orders o ON inv.order_id = o.id
                WHERE o.order_id = :order_id"""

            rows = execute_raw_sql_readonly(sql, {'order_id': order_id})
            return rows
        except Exception as e:
            logger.error(f"invoice_fetch_error | order_id={order_id} error={e}", exc_info=True)
            raise
