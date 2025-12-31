"""
Order creation functions
"""
from typing import Dict, List
from decimal import Decimal

from fastapi import HTTPException, BackgroundTasks, Request

from app.services.order_service import OrderService
from app.services.order_meta_service import OrderMetaService
from app.repository.orders import OrdersRepository
from app.utils.order_utils import block_quantity_in_redis, block_quantity_in_typesense
from app.logging.utils import get_app_logger
from app.config.settings import OMSConfigs

configs = OMSConfigs()

logger = get_app_logger("app.core.orders_creation.creation")


async def create_order_for_facility(
    order_data_dict: Dict,
    facility_name: str,
    facility_items: List[Dict],
    facility_total: Decimal,
    parent_order_id: str,
    promotion_result: Dict,
    origin: str,
    request: Request,
    background_tasks: BackgroundTasks,
    stock_check_enabled: bool,
    **kwargs
) -> Dict:
    """
    Create order for a single facility
    
    Returns: Dict with internal_order_id, order_id, facility_name, total_amount
    """
    service = OrderService()
    orders_repository = OrdersRepository()
    
    facility_order_data = order_data_dict.copy()
    facility_order_data['items'] = facility_items
    facility_order_data['facility_name'] = facility_name
    facility_order_data['total_amount'] = facility_total
    facility_order_data['delivery_charge'] = kwargs.get('delivery_charge', 0.0)
    facility_order_data['packaging_charge'] = kwargs.get('packaging_charge', 0.0)
    
    facility_order_data['marketplace'] = facility_items[0].get('marketplace', 'ROZANA')
    facility_order_data['original_total_amount'] = sum(Decimal(str(item.get("original_sale_price", 0))) * Decimal(str(item.get("quantity", 0))) for item in facility_items)
    facility_order_data['promotion_result'] = promotion_result
    
    eta_data = order_data_dict.get('eta_data')
    if eta_data and facility_name in eta_data:
        facility_order_data['eta'] = eta_data.get(facility_name, facility_order_data['eta'])
    
    # Create order
    result = await service.create_order(
        facility_order_data, 
        origin, 
        biller_id=kwargs.get("biller_id", ""), 
        biller_name=kwargs.get("biller_name", "")
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=f"Failed to create order for {facility_name}")
    
    internal_order_id = result["id"]
    order_id = result["order_id"]
    
    # Set parent_order_id
    orders_repository.update_parent_order_id(internal_order_id, parent_order_id)
    
    # Convert skip list to lowercase strings for comparison
    skip_list_lower = [str(m).strip().lower() for m in configs.STOCK_SKIP_CHECK]
    marketplace_str = str(facility_order_data['marketplace']).strip().lower()

    # Save order metadata
    try:
        metadata = order_data_dict.get('metadata', {})
        OrderMetaService.save_order_metadata(internal_order_id, request, origin, metadata)
    except Exception as exc:
        logger.error(f"order_metadata_save_failed | order_internal_id={internal_order_id} error={exc}")
    
    # Block stock for this facility
    if stock_check_enabled and origin == "app" and marketplace_str not in skip_list_lower:
        bulk_update_data = await block_quantity_in_redis(facility_items, facility_name)
        if bulk_update_data:
            background_tasks.add_task(block_quantity_in_typesense, bulk_update_data, facility_name)
    
    logger.info(f"Created order {order_id} for facility {facility_name} | amount={facility_total}")
    
    return {
        'internal_order_id': internal_order_id,
        'order_id': order_id,
        'facility_name': facility_name,
        'total_amount': facility_total
    }
