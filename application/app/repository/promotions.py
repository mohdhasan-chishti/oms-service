import time
from typing import Dict, Optional

# services
from app.services.typesense_service import TypesenseService

# Database connection
from app.connections.database import execute_raw_sql_readonly

from app.logging.utils import get_app_logger
logger = get_app_logger("app.promotions_repository")


class PromotionsRepository:
    async def get_promotion_by_code(self, promotion_code: str, facility_name: str) -> Optional[Dict]:
        try:
            now_ts = int(time.time())
            filter_by = f"promotion_code:={promotion_code} && is_active:=true && start_date:<={now_ts} && end_date:>={now_ts} && facility_code:={facility_name}"

            params = {"q": "*", "query_by": "name,description", "filter_by": filter_by, "per_page": 1}
            typesense_service = TypesenseService()
            result = await typesense_service.search_documents(params, "promotions")
            hits = result.get("hits", [])
            logger.info(f"get_promotion_by_code_result | code={promotion_code} facility={facility_name} hits={len(hits)}")
            return hits[0]["document"] if hits else None
        except Exception as e:
            logger.error(f"get_promotion_by_code_error | code={promotion_code} facility={facility_name} error={e}", exc_info=True)
            raise

    async def get_promotion_by_coupon_code(self, coupon_code: str, facility_name: str) -> Optional[Dict]:
        try:
            now_ts = int(time.time())
            filter_by = f"coupon_code:={coupon_code} && offer_type:=coupon && is_active:=true && start_date:<={now_ts} && end_date:>={now_ts} && facility_code:={facility_name}"

            params = {"q": "*", "query_by": "name,description", "filter_by": filter_by, "per_page": 1}
            typesense_service = TypesenseService()
            result = await typesense_service.search_documents(params, "promotions")
            hits = result.get("hits", [])
            logger.info(f"get_promotion_by_coupon_code_result | coupon={coupon_code} facility={facility_name} hits={len(hits)}")
            return hits[0]["document"] if hits else None
        except Exception as e:
            logger.error(f"get_promotion_by_coupon_code_error | coupon={coupon_code} facility={facility_name} error={e}", exc_info=True)
            raise

    async def get_promotion_smart(self, code: str, facility_name: str, promotion_type: Optional[str] = None) -> Optional[Dict]:
        try:
            if promotion_type == "coupon":
                promotion_doc = await self.get_promotion_by_coupon_code(code, facility_name)
                if not promotion_doc:
                    promotion_doc = await self.get_promotion_by_code(code, facility_name)
            else:
                promotion_doc = await self.get_promotion_by_code(code, facility_name)
                if not promotion_doc:
                    promotion_doc = await self.get_promotion_by_coupon_code(code, facility_name)
            
            logger.info(f"get_promotion_smart_result | code={code} type={promotion_type} found={promotion_doc is not None}")
            return promotion_doc
        except Exception as e:
            logger.error(f"get_promotion_smart_error | code={code} type={promotion_type} error={e}", exc_info=True)
            raise

    async def get_user_orders_count(self, user_id: str) -> int:
        try:
            query = "SELECT COUNT(*) as count FROM orders WHERE customer_id = :user_id and status not in (0, 10)"
            rows = execute_raw_sql_readonly(query, {"user_id": user_id})
            logger.info(f"get_user_orders_count_result | user_id={user_id} count={rows}")
            return rows[0].get("count", 0) if rows else 0
        except Exception as e:
            logger.error(f"get_user_orders_count_error | user_id={user_id} error={e}", exc_info=True)
            raise

    async def get_user_orders_count_by_channel(self, user_id: str, channel: str) -> int:
        try:
            query = "SELECT COUNT(*) as count FROM orders WHERE customer_id = :user_id AND order_mode = :channel"
            rows = execute_raw_sql_readonly(query, {"user_id": user_id, "channel": channel})
            logger.info(f"get_user_orders_count_by_channel_result | user_id={user_id} channel={channel} count={rows}")
            return rows[0].get("count", 0) if rows else 0
        except Exception as e:
            logger.error(f"get_user_orders_count_by_channel_error | user_id={user_id} channel={channel} error={e}", exc_info=True)
            raise

    async def get_coupon_total_usage(self, coupon_code: str) -> int:
        try:
            query = "SELECT COUNT(*) as count FROM orders WHERE promotion_code = :code"
            rows = execute_raw_sql_readonly(query, {"code": coupon_code})
            logger.info(f"get_coupon_total_usage_result | code={coupon_code} count={rows}")
            return rows[0].get("count", 0) if rows else 0
        except Exception as e:
            logger.error(f"get_coupon_total_usage_error | code={coupon_code} error={e}", exc_info=True)
            raise

    async def get_coupon_user_usage(self, coupon_code: str, user_id: str) -> int:
        try:
            query = "SELECT COUNT(*) as count FROM orders WHERE promotion_code = :code AND customer_id = :user_id"
            rows = execute_raw_sql_readonly(query, {"code": coupon_code, "user_id": user_id})
            logger.info(f"get_coupon_user_usage_result | code={coupon_code} user_id={user_id} count={rows}")
            return rows[0].get("count", 0) if rows else 0
        except Exception as e:
            logger.error(f"get_coupon_user_usage_error | code={coupon_code} user_id={user_id} error={e}", exc_info=True)
            raise
