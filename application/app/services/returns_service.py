from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional
import random
import string

from sqlalchemy import text

from app.connections.database import get_raw_transaction
from app.models.common import get_ist_now
from app.logging.utils import get_app_logger

logger = get_app_logger(__name__)


def _generate_return_reference() -> str:
    # Example: RTN-25082417-A9ZQ (YYMMDDHH + 4 random)
    now = get_ist_now()
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"RTN-{now.strftime('%y%m%d%H')}-{rand}"


class ReturnsService:
    @staticmethod
    def create_return(
        order_id: str,
        items: List[Dict],
        return_reason: Optional[str],
        comments: Optional[str],
        refund_mode: Optional[str] = None,
    ) -> Dict:
        """
        Persist a return and its items using a single DB transaction.

        Input items format: [{'sku': str, 'quantity': Decimal|int}]
        Output:
        {
          'return_reference': str,
          'return_id': int,
          'total_refund_amount': Decimal,
          'returned_items': [{'sku': str, 'quantity_returned': int, 'refund_amount': Decimal}]
        }
        """
        returned_items_out: List[Dict] = []
        total_refund: Decimal = Decimal('0.00')

        with get_raw_transaction() as conn:
            # Resolve internal order PK and customer_id using customer-facing order_id
            order_row = conn.execute(
                text("SELECT id, customer_id FROM orders WHERE order_id = :oid"),
                {'oid': order_id},
            ).fetchone()
            if not order_row:
                logger.warning(f"create_return_order_not_found | order_id={order_id}")
                raise ValueError(f"Order {order_id} not found when creating return")

            order_pk = order_row.id
            customer_id = order_row.customer_id
            return_reference = _generate_return_reference()


            # Insert returns row
            insert_returns_sql = """
                INSERT INTO returns (
                    return_reference, sale_return_id, order_id, customer_id, return_type, return_reason, comments,
                    return_method, status, total_refund_amount, refund_mode, refund_status,
                    approved_at, processed_at, completed_at, created_at, updated_at
                ) VALUES (
                    :return_reference, '', :order_pk, :customer_id, :return_type, :return_reason, :comments,
                    'api', 'approved', :total_refund_amount, :refund_mode, 'pending',
                    NULL, NULL, NULL, NOW(), NOW()
                )
                RETURNING id
            """
            # Decide return_type based on whether the caller supplied multiple items or a full-return flag externally.
            # If the caller wants to avoid deriving a variable, we can persist without relying on it elsewhere.
            return_type = 'full' if len(items) > 0 and all('quantity' in it for it in items) else 'partial'  # keep schema satisfied
            # Note: The above keeps a value in DB; the API response can choose to omit if unnecessary.

            ret_result = conn.execute(
                text(insert_returns_sql),
                {
                    'return_reference': return_reference,
                    'order_pk': order_pk,
                    'customer_id': customer_id,
                    'return_type': return_type,
                    'return_reason': return_reason,
                    'comments': comments,
                    'total_refund_amount': Decimal('0.00'),
                    'refund_mode': refund_mode,
                },
            )
            ret_row = ret_result.fetchone()
            if not ret_row:
                logger.error(f"create_return_insert_failed | order_id={order_id}")
                raise RuntimeError("Failed to create returns row")
            return_id = ret_row.id

            # Per-item inserts
            for it in items:
                sku = it['sku']
                qty = it['quantity']
                # Convert to Decimal for precise calculations
                qty_decimal = Decimal(str(qty))

                # Fetch order_item data for pricing
                oi_row = conn.execute(
                    text(
                        """
                        SELECT id, unit_price, sale_price
                        FROM order_items
                        WHERE order_id = :order_pk AND sku = :sku
                        """
                    ),
                    {'order_pk': order_pk, 'sku': sku},
                ).fetchone()
                if not oi_row:
                    logger.warning(f"create_return_item_not_found | order_id={order_id} sku={sku}")
                    raise ValueError(f"Order item not found for SKU {sku}")

                unit_price = Decimal(oi_row.unit_price)
                sale_price = Decimal(oi_row.sale_price)
                refund_amount = (sale_price * qty_decimal).quantize(Decimal('0.01'))

                # Insert return_items
                conn.execute(
                    text(
                        """
                        INSERT INTO return_items (
                            return_id, order_item_id, sku, quantity_returned,
                            unit_price, sale_price, refund_amount, return_reason,
                            item_condition, condition_notes, status, created_at, updated_at
                        ) VALUES (
                            :return_id, :order_item_id, :sku, :quantity_returned,
                            :unit_price, :sale_price, :refund_amount, :return_reason,
                            NULL, NULL, 'approved', NOW(), NOW()
                        )
                        """
                    ),
                    {
                        'return_id': return_id,
                        'order_item_id': oi_row.id,
                        'sku': sku,
                        'quantity_returned': qty_decimal,
                        'unit_price': unit_price,
                        'sale_price': sale_price,
                        'refund_amount': refund_amount,
                        'return_reason': return_reason,
                    },
                )

                returned_items_out.append({
                    'sku': sku,
                    'quantity_returned': float(qty_decimal),
                    'refund_amount': float(refund_amount),
                    'line_reference': str(it['line_reference']) if it.get('line_reference') is not None else " "
                })
                total_refund += refund_amount

            # Update total_refund_amount in returns
            conn.execute(
                text(
                    """
                    UPDATE returns
                    SET total_refund_amount = :total_refund, updated_at = NOW()
                    WHERE id = :rid
                    """
                ),
                {'total_refund': total_refund, 'rid': return_id},
            )

            conn.commit()
            logger.info(
                f"return_persisted | order_id={order_id} return_id={return_id} return_reference={return_reference} items={len(items)} total_refund={total_refund}"
            )

        return {
            'return_reference': return_reference,
            'return_id': return_id,
            'total_refund_amount': float(total_refund),
            'returned_items': returned_items_out
        }