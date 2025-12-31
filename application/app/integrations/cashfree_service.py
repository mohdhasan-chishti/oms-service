"""
Cashfree service for payment integration.
"""
import json
import requests
from typing import Dict, Any, Optional
from decimal import Decimal

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("cashfree_service")

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()


class CashfreeService:
    """Cashfree service for payment operations"""
    
    def __init__(self):
        self.app_id = configs.CASHFREE_APP_ID or "TEST_APP_ID"
        self.secret_key = configs.CASHFREE_SECRET_KEY or "TEST_SECRET_KEY"
        self.integration_enabled = getattr(configs, 'CASHFREE_INTEGRATION_ENABLED', True)
        
        # Handle base URL - remove trailing /pg if present, then add /pg/orders
        base = getattr(configs, 'CASHFREE_BASE_URL', 'https://sandbox.cashfree.com').rstrip('/pg')
        self.base_url = base + "/pg/orders"
        
        # Webhook and return URLs from config
        self.webhook_url = getattr(configs, 'CASHFREE_WEBHOOK_URL', '')
        self.return_url = getattr(configs, 'CASHFREE_RETURN_URL', '')
        
        self.currency = getattr(configs, 'CASHFREE_CURRENCY', 'INR')
        self.timeout = getattr(configs, 'CASHFREE_TIMEOUT', 30)
        self.initialized = True
        
        # Set headers for API requests
        self.headers = {
            "x-api-version": "2023-08-01",
            "Content-Type": "application/json",
            "x-client-id": self.app_id,
            "x-client-secret": self.secret_key,
            "accept": "application/json"
        }
        
        logger.info(f"Cashfree service initialized | app_id={self.app_id} | base_url={self.base_url}")

    def create_order(
        self,
        order_id: str,
        amount: Decimal,
        customer_details: Dict[str, Any],
        customer_phone: str = None,
        customer_email: str = None,
        notes: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a Cashfree payment order
        """
        logger.info(f"Creating Cashfree order | order_id={order_id} | amount={amount}")
        
        # Prepare payload according to Cashfree API requirements
        payload = {
            "order_id": order_id,
            "order_amount": float(amount),
            "order_currency": self.currency,
            "customer_details": {
                "customer_id": str(customer_details.get('customer_id', 'guest')),
                "customer_phone": str(customer_phone or customer_details.get('customer_phone') or '9999999999'),
                "customer_email": str(customer_email or customer_details.get('customer_email') or 'test@example.com'),
                "customer_name": str(customer_details.get('customer_name', 'Customer'))
            }
        }
        
        # Add notes
        if notes:
            payload["order_tags"] = notes
            logger.info(f"Adding order_tags to Cashfree order | notes={notes}")
        
        if self.return_url and self.webhook_url:
            payload["order_meta"] = {"return_url": self.return_url, "notify_url": self.webhook_url}
        
        try:
            logger.info(f"Creating Cashfree order request")
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            logger.info(f"Cashfree API response | status_code: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Cashfree order created successfully | order_id={order_id} | cf_order_id={data.get('cf_order_id')}")
                logger.info(f"Full Cashfree response: {json.dumps(data, indent=2)}")
                return data
            else:
                # Log the actual response for debugging
                try:
                    error_data = response.json()
                    logger.error(f"Cashfree API failed | status: {response.status_code} | response: {error_data}")
                except:
                    logger.error(f"Cashfree API failed | status: {response.status_code} | response: {response.text}")
                
                # Log the full error response for debugging
                error_msg = f"Cashfree API failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"Cashfree API error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(f"Failed to create Cashfree order: {str(e)}")

