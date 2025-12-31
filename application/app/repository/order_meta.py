"""
Order Meta Repository for raw SQL operations
"""

from typing import Optional, Dict, Any
from sqlalchemy import text
from app.connections.database import get_raw_transaction
from app.logging.utils import get_app_logger

logger = get_app_logger("app.order_meta_repository")


class OrderMetaRepository:
    """Repository for order metadata database operations using raw SQL"""

    def create_order_meta(self, order_id: int, client_ip: Optional[str] = None, user_agent: Optional[str] = None, device: Optional[str] = None,
                        platform: Optional[str] = None, app_version: Optional[str] = None, web_version: Optional[str] = None,
                        longitude: Optional[float] = None, latitude: Optional[float] = None) -> None:
        """
        Create an order metadata record using raw SQL.
        """
        # Stores web_version if present, otherwise app_version in the version column.
        version = web_version or app_version or None
        insert_query = text("""
            INSERT INTO order_metadata (
                order_id, client_ip, user_agent, device, platform, version,
                longitude, latitude, created_at, updated_at
            ) VALUES (
                :order_id, :client_ip, :user_agent, :device, :platform, :version,
                :longitude, :latitude, NOW(), NOW()
            )
            RETURNING id, created_at
        """)

        try:
            params = {
                "order_id": order_id,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "device": device,
                "platform": platform,
                "version": version,
                "longitude": longitude or 0.00,
                "latitude": latitude or 0.00,
            }
            with get_raw_transaction() as conn:
                result = conn.execute(insert_query, params)

                # Fetch result before commit
                row = result.fetchone()
                conn.commit()

                meta_record_id, created_at = row if row else (None, None)

            # Pass app_version and web_version explicitly in extra for logging
            logger.info(f"order_meta_created | id={meta_record_id} order_id={order_id} client_ip={client_ip} platform={platform} version={version}",extra={'app_version': app_version or '', 'web_version': web_version or ''})

        except Exception as e:
            logger.error(f"order_meta_create_error | order_id={order_id} client_ip={client_ip} error={e}")
            raise e