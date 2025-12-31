import httpx
import os
from fastapi import HTTPException
from app.middlewares.token_validation import TokenValidationService
from app.services.order_query_service import OrderQueryService
from app.services.refund_query_service import RefundQueryService
from app.core.order_cancel import cancel_order_core
from app.validations.orders import OrderUserValidator
from typing import List, Dict
from app.core.order_functions import get_all_orders_core
from app.utils.firebase_utils import get_customer_id_from_phone_number

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)


async def validate_token_and_get_orders(token: str, customer_id: str, page_size: int = 20, page: int = 1, sort_order: str = "desc", search: str = None):
    token_service = TokenValidationService()
    is_valid = await token_service.validate_token(token)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        service = OrderQueryService()
        result = service.get_orders_by_customer_id(customer_id, page_size, page, sort_order, search)
        
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting orders for customer %s: %s", customer_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

async def validate_token_and_get_order_items(token: str, customer_id: str, order_id: str):
    token_service = TokenValidationService()
    is_valid = await token_service.validate_token(token)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        service = OrderQueryService()
        
        logger.info(f"Looking up order_id: {order_id} for customer: {customer_id}")
        order = service.get_order_by_id(order_id)
        logger.info(f"Order lookup result: {order}")
        
        if not order:
            logger.warning(f"Order {order_id} not found in database")
            raise HTTPException(status_code=404, detail="Order not found or access denied")
        
        if order.get('customer_id') != customer_id:
            logger.warning(f"Order {order_id} belongs to customer {order.get('customer_id')}, not {customer_id}")
            raise HTTPException(status_code=404, detail="Order not found or access denied")
        
        return service.get_order_items_by_order_id(order_id)
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting order items for order %s, customer %s: %s", order_id, customer_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

async def validate_token_and_cancel_order(token: str, customer_id: str, order_id: str, cancel_reason: str = None, cancel_remarks: str = None):
    try:
        # Validate that the order belongs to the customer (same as app route)
        order_validator = OrderUserValidator(order_id=order_id, user_id=customer_id)
        order_validator.validate_order_with_user()

        # Cancel the order
        result = await cancel_order_core(order_id, cancel_reason, cancel_remarks)
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error cancelling order %s for customer %s: %s", order_id, customer_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


async def validate_token_and_return_items(token: str, customer_id: str, order_id: str, items_to_return: List[Dict]):
    """
    Validate token and return specific items from an order.
    
    Args:
        token: Authentication token
        customer_id: Customer ID for validation
        order_id: Order ID to return items from
        items_to_return: List of items with sku and quantity to return
    """
    token_service = TokenValidationService()
    is_valid = await token_service.validate_token(token)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        service = OrderQueryService()
        order = service.get_order_by_id(order_id)
        
        if not order or order.get('customer_id') != customer_id:
            raise HTTPException(status_code=404, detail="Order not found or access denied")
        
        # result = await return_order_items_core(order_id, items_to_return)
        # return result
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error returning items from order %s for customer %s: %s", order_id, customer_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


async def validate_token_and_return_full_order(token: str, customer_id: str, order_id: str):
    """
    Validate token and return all items in an order.
    
    Args:
        token: Authentication token
        customer_id: Customer ID for validation
        order_id: Order ID to return completely
    """
    token_service = TokenValidationService()
    is_valid = await token_service.validate_token(token)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        service = OrderQueryService()
        order = service.get_order_by_id(order_id)
        
        if not order or order.get('customer_id') != customer_id:
            raise HTTPException(status_code=404, detail="Order not found or access denied")
        
        # result = await return_full_order_core(order_id)
        # return result
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error returning full order %s for customer %s: %s", order_id, customer_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

async def get_orders_by_phone_number(phone_number: str, page_size: int = 20, page: int = 1, sort_order: str = "desc", search: str = None):
    try:
        customer_id = await get_customer_id_from_phone_number(phone_number)
        service = OrderQueryService()
        result = service.get_orders_by_customer_id(customer_id, page_size, page, sort_order, search)
        
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting orders for phone number %s: %s", phone_number, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    
async def get_refund_details_by_phone_number(phone_number: str):
    try:
        customer_id = await get_customer_id_from_phone_number(phone_number)
        service = RefundQueryService()
        result = service.get_refunds_by_customer_id(customer_id)
        
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting refund details for phone number %s: %s", phone_number, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc