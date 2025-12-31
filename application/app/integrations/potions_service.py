import httpx
from httpx_retry import AsyncRetryTransport, RetryPolicy
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.core.constants import OrderStatus

# Redis token cache
from app.connections.redis_wrapper import RedisJSONWrapper

# Request context
from app.middlewares.request_context import request_context

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("potions_service")

# Settings
from app.config.settings import OMSConfigs
from app.repository.orders import OrdersRepository

order_repository = OrdersRepository()
configs = OMSConfigs()

class PotionsServiceReturnMessage(BaseModel):
    success: bool
    message: str
    task_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class PotionsService:
    """Service for integrating with Potions WMS API"""

    def __init__(self):
        self.potions_config = configs.POTIONS_INTEGRATION_ENABLED
        self.potions_base_url = configs.POTIONS_BASE_URL
        self.potions_client_id = configs.POTIONS_CLIENT_ID
        self.potions_client_secret = configs.POTIONS_CLIENT_SECRET
        self.timeout = configs.POTIONS_TIMEOUT

        # Redis client for token caching
        self.token_cache_db = configs.REDIS_CACHE_DB
        self._redis = RedisJSONWrapper(database=self.token_cache_db)
        self._token_key = "potions:oauth:access_token"

        if not (self.potions_config and self.potions_base_url and self.potions_client_id and self.potions_client_secret):
            logger.error("Potions integration is disabled or not configured")
            raise ValueError("Potions integration is disabled or not configured")

        # Configure retry policy for Potions API calls
        retry_policy = RetryPolicy(
            max_retries=5,
            initial_delay=0.5,
            multiplier=2.0,
            retry_on=[429, 500, 502, 503, 504]
        )
        # Create retry transport
        retry_transport = AsyncRetryTransport(policy=retry_policy)

        # Persistent async client with retry support
        self.client = httpx.AsyncClient(transport=retry_transport, timeout=self.timeout)

    async def close(self):
        """Explicitly close the HTTP client to free resources."""
        await self.client.aclose()

    def return_message(self, success: bool, message: str, task_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> PotionsServiceReturnMessage:
        return PotionsServiceReturnMessage(success=success, message=message, task_id=task_id, data=data)

    async def _make_request_with_retry(self, endpoint: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, context_info: str = "", custom_headers: Optional[Dict[str, str]] = None) -> PotionsServiceReturnMessage:
        """Make HTTP request with automatic retry and token refresh on 401.

        Note: Network-level retries (429, 500, 502, 503, 504) are handled automatically 
        by httpx-retry transport. This method only handles 401 token refresh logic.

        Args:
            endpoint: API endpoint URL
            payload: Request payload
            headers: Optional pre-built headers (if None, will fetch OAuth headers)
            context_info: Context information for logging
            custom_headers: Additional headers to merge with OAuth headers (e.g., warehouse header)
        """
        # Build headers
        if headers is None:
            headers = await self._get_headers()
            if custom_headers:
                headers.update(custom_headers)
        try:
            resp = await self.client.post(endpoint, headers=headers, json=payload)

            if resp.status_code == 401:
                logger.warning(f"potions_api_401_retrying | {context_info}")
                try:
                    self._redis.delete(self._token_key)
                except Exception:
                    pass

                # Refresh headers and retry
                headers = await self._get_headers()
                if custom_headers:
                    headers.update(custom_headers)
                resp = await self.client.post(endpoint, headers=headers, json=payload)

            if resp.status_code in (200, 201, 202):
                data = resp.json() if resp.content else {}
                return self.return_message(success=True, task_id=data.get('task_id'), message=data.get('message', 'Success'), data=data)
            # Other error responses
            logger.error(f"potions_api_failed | {context_info} status_code={resp.status_code} error={resp.text}")
            return self.return_message(success=False, message=f"potions_api_{resp.status_code}", task_id=None)

        except httpx.HTTPStatusError as e:
            # Network errors after all retries exhausted (handled by httpx-retry)
            if e.response.status_code in [429, 500, 502, 503, 504]:
                logger.error(f"Potions API: All retries exhausted - HTTP {e.response.status_code} for POST {endpoint} | {context_info}")
            else:
                logger.error(f"Potions API: HTTP {e.response.status_code} error for POST {endpoint} | {context_info}")
            return self.return_message(success=False, message=f"potions_api_{e.response.status_code}", task_id=None)
        except Exception as e:
            logger.error(f"Potions API: Unexpected error for POST {endpoint} | {context_info} | error={str(e)}", exc_info=True)
            return self.return_message(success=False, message=f"potions_api_error: {str(e)}", task_id=None)

    async def _get_headers(self) -> Dict[str, str]:
        token = await self._get_oauth_token()
        if not token:
            logger.error("Unable to obtain OAuth token")
            raise ValueError("Unable to obtain OAuth token")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

    async def _get_oauth_token(self) -> str:
        """Return cached token or fetch and cache a new one (minimal flow)."""
        try:
            # Try cache
            if self._redis and self._redis.connected:
                cached = self._redis.get(self._token_key)
                if cached:
                    return cached

            # Fetch new
            token_endpoint = f"{self.potions_base_url}/o/token/"
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.potions_client_id,
                "client_secret": self.potions_client_secret,
            }
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}

            # Use the persistent client with retry support
            resp = await self.client.post(token_endpoint, headers=headers, data=token_data)

            if resp.status_code != 200:
                logger.error(f"[POTIONS_OAUTH_FAILED] | status_code={resp.status_code}")
                return None
            data = resp.json()
            token = data.get('access_token')
            exp = data.get('expires_in', 300)
            ttl = max(int(exp) - 60, 60) if isinstance(exp, int) else 300
            if token and self._redis and self._redis.connected:
                try:
                    self._redis.set_with_ttl(self._token_key, token, ttl)
                except Exception:
                    pass
            return token
        except Exception as e:
            logger.error(f"[[POTIONS_OAUTH_FAILED] | error={str(e)}", exc_info=True)
            return None

    async def sync_order_by_id(self, facility_name: str, order_id: str, order_service) -> PotionsServiceReturnMessage:
        """Sync order to Potions WMS API by order ID"""
        try:
            request_context.module_name = 'potions_service'
            # Call Potions API to trigger WMS sync
            result = await self._trigger_potions_sync(order_id)
            
            if result.success:
                # Update order status to POTIONS_SYNCED (18)
                current_status = order_repository.get_order_status_by_order_id(order_id)
                if current_status <= 19:
                    order_repository.update_order_and_items_status_by_order_id(order_id, OrderStatus.POTIONS_SYNCED)
                logger.info(f"potions_sync_success | order_id={order_id} facility_name={facility_name} task_id={result.task_id}")
                return self.return_message(success=True, message="Order synced to Potions WMS successfully", task_id=result.task_id)
            else:
                # Update order status to POTIONS_SYNC_FAILED (19)
                order_repository.update_order_and_items_status_by_order_id(order_id, OrderStatus.POTIONS_SYNC_FAILED)
                logger.error(f"potions_sync_failed | order_id={order_id} facility_name={facility_name} error={result.message}")
                return self.return_message(success=False, message=f"Failed to sync order to Potions WMS: {result.message}", task_id=result.task_id)

        except Exception as e:
            # Update order status to POTIONS_SYNC_FAILED (19) on exception
            try:
                order_repository.update_order_and_items_status_by_order_id(order_id, OrderStatus.POTIONS_SYNC_FAILED)
                logger.error(f"potions_sync_exception | order_id={order_id} facility_name={facility_name} error={e}", exc_info=True)
            except Exception as e:
                logger.error(f"potions_sync_exception | order_id={order_id} facility_name={facility_name} error={e}", exc_info=True)
            return self.return_message(success=False, message="Exception occurred while syncing to Potions WMS", task_id=None)

    async def _trigger_potions_sync(self, order_id: str) -> PotionsServiceReturnMessage:
        """Trigger Potions WMS sync via API call with automatic retry support."""
        try:
            request_context.module_name = 'potions_service'
            payload = {"order_id": order_id}
            endpoint = f"{self.potions_base_url}/api/potions/integrations/order/create/"

            result = await self._make_request_with_retry(endpoint=endpoint, payload=payload, context_info=f"order_id={order_id}")

            if result.success:
                result.message = "Order sync triggered"

            return result
        except Exception as e:
            logger.error(f"potions_wms_api_exception | order_id={order_id} error={e}", exc_info=True)
            return self.return_message(success=False, message=str(e), task_id=None)


    async def create_reverse_consignment_by_return_reference(self, return_reference: str, order_id: str = None) -> PotionsServiceReturnMessage:
        """Trigger reverse consignment creation in Potions by return reference.

        Prefers OAuth token; falls back to POTIONS_BEARER_TOKEN if OAuth not configured/available.
        Performs a single retry on 401 by invalidating cached OAuth token.
        Handles all errors internally and logs appropriately.
        """
        try:
            request_context.module_name = 'potions_service'
            endpoint = f"{self.potions_base_url}/api/potions/integrations/consignment/create_reverse/return_reference/"
            payload = {"return_reference": return_reference}
            
            result = await self._make_request_with_retry(endpoint=endpoint,payload=payload,context_info=f"order_id={order_id} return_reference={return_reference}")

            if result.success:
                logger.info("potions_reverse_consignment_triggered | order_id=%s return_reference=%s status=%s task_id=%s", order_id, return_reference, "reverse_consignment_triggered", result.task_id)
                result.message = "Reverse consignment triggered in Potions"
            else:
                logger.error("potions_reverse_consignment_failed | order_id=%s return_reference=%s error=%s", order_id, return_reference, result.message)

            return result
        except Exception as e:
            logger.error("potions_reverse_consignment_error | order_id=%s return_reference=%s error=%s", order_id, return_reference, str(e), exc_info=True)
            return self.return_message(success=False, message=str(e), task_id=None)

    async def cancel_outbound_order(self, order_reference: str, warehouse: str) -> PotionsServiceReturnMessage:
        """Cancel order in Potions WMS with automatic retry support"""
        try:
            endpoint = f"{self.potions_base_url}/api/potions/integrations/order/cancel/"
            payload = {
                "order_reference": order_reference,
                "facility_id": warehouse
            }

            logger.info(f"potions_cancel_api_call | endpoint={endpoint} order_reference={order_reference} warehouse={warehouse} payload={payload}")
            
            result = await self._make_request_with_retry(endpoint=endpoint, payload=payload, context_info=f"order_reference={order_reference} warehouse={warehouse}")

            if result.success:
                logger.info(f"potions_cancel_api_success | order_reference={order_reference} response={result.data}")
                result.message = "Order cancellation triggered successfully in Potions WMS"
            else:
                logger.error(f"potions_cancel_api_error | order_reference={order_reference} error={result.message}")

            return result
        except Exception as e:
            logger.error(f"potions_cancel_api_exception | order_reference={order_reference} error={e}", exc_info=True)
            return self.return_message(success=False, message=str(e), task_id=None)

    async def create_sales_return(self, return_reference: str, warehouse: str = None) -> PotionsServiceReturnMessage:
        """Create sales return in Potions WMS for POS orders with automatic retry support"""
        try:
            request_context.module_name = 'potions_service'
            endpoint = f"{self.potions_base_url}/api/potions/integrations/sales-return/"
            payload = {"return_reference": return_reference}
            
            # Add warehouse header if provided
            custom_headers = {"warehouse": warehouse} if warehouse else None
            
            result = await self._make_request_with_retry(endpoint=endpoint, payload=payload, context_info=f"return_reference={return_reference} warehouse={warehouse}", custom_headers=custom_headers)

            if result.success:
                logger.info(f"potions_sales_return_created | return_reference={return_reference} warehouse={warehouse} message={result.message}")
                # Enhance result data
                if result.data:
                    result.data["status"] = "sale_return_triggered"
                result.message = result.data.get('message', 'Sales return created successfully') if result.data else 'Sales return created successfully'
            else:
                logger.error(f"potions_sales_return_failed | return_reference={return_reference} warehouse={warehouse} error={result.message}")
                result.message = f"Failed to create sales return: {result.message}"

            return result
        except Exception as e:
            logger.error(f"potions_sales_return_exception | return_reference={return_reference} warehouse={warehouse} error={str(e)}", exc_info=True)
            return self.return_message(success=False, message=f"Exception creating sales return: {str(e)}", task_id=None)

    async def process_return(self, return_data: Dict[str, Any]) -> PotionsServiceReturnMessage:
        """Process return in Potions WMS (placeholder for future implementation)"""
        logger.info(f"potions_return_not_implemented | return_data_keys={list((return_data or {}).keys())}")
        return self.return_message(success=True, message="Return processing not implemented in Potions WMS - handled in OMS only", task_id=None)
