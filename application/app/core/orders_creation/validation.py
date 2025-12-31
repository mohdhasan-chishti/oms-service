"""
Order validation functions
"""
from decimal import Decimal
from typing import Dict, List, Tuple

from fastapi import HTTPException

from app.validations.typesense import TypesenseValidator
from app.validations.orders import OrderCreateValidator
from app.validations.stock import StockValidator
from app.validations.payment_validations import PaymentValidator
from app.logging.utils import get_app_logger
from app.config.settings import OMSConfigs

configs = OMSConfigs()

logger = get_app_logger("app.core.orders_creation.validation")


def validate_order_and_payment(order, user_id: str, origin: str) -> OrderCreateValidator:
    """
    Perform all order and payment validations
    
    Args:
        order: OrderCreate object
        user_id: User ID from request
        origin: Origin of the request (app/pos)
    
    Returns:
        OrderCreateValidator: The validator instance
    """
    # Validation Layer
    validator = OrderCreateValidator(order, user_id)
    validator.validate_items_count()
    validator.validate_duplicate_sku_items()
    validator.validate_quantity(origin)
    validator.validate_pos_extra_quantity(origin)
    validator.validate_user_type()

    # Payment Validation Layer
    payment_validator = PaymentValidator(order)
    payment_validator.validate_payment_configuration(origin)
    
    logger.info(f"Order and payment validations passed | user_id={user_id} origin={origin}")
    return validator




async def validate_and_enrich_facility(
    facility_items: List,
    facility_name: str,
    user_type: str,
    origin: str,
    promotion_type: str
) -> Tuple[List[Dict], Decimal]:
    """
    Validate and enrich items for a single facility.
    Returns: (enriched_items, enriched_total)
    """
    typesense_validator = TypesenseValidator(user_type=user_type)
    
    # Calculate facility total
    facility_total = sum(Decimal(str(item.sale_price)) * Decimal(str(item.quantity)) for item in facility_items)
    
    # Typesense validation
    products, validation_errors = await typesense_validator.validate_items(
        facility_items, facility_name, order_amount=facility_total, origin=origin, promotion_type=promotion_type
    )
    if validation_errors:
        raise HTTPException(status_code=400, detail=f"Validation failed for {facility_name}: {validation_errors}")
    
    # Typesense enrichment
    enriched_items, enrich_errors = await typesense_validator.enrich_items(facility_items, products, facility_name)
    if enrich_errors:
        raise HTTPException(status_code=400, detail=f"Enrichment failed for {facility_name}: {enrich_errors}")

    # Calculate enriched total using original_sale_price
    enriched_total = Decimal('0')
    for item in enriched_items:
        enriched_total += Decimal(str(item.get("sale_price", 0))) * Decimal(str(item.get("quantity", 0)))

    logger.info(f"Validated facility | facility={facility_name} | items={len(enriched_items)} | total={enriched_total}")

    return enriched_items, enriched_total


def validate_facility_stock(enriched_items: List[Dict], facility_name: str):
    """Validate stock for a facility's items."""
    # Aggregate quantities by wh_sku to handle duplicates and collect item names
    wh_sku_data = {}
    for item in enriched_items:
        # Skip stock check for marketplaces in STOCK_SKIP_CHECK
        marketplace = item.get("marketplace", "").strip().lower()
        skip_list_lower = [str(m).strip().lower() for m in configs.STOCK_SKIP_CHECK] if configs.STOCK_SKIP_CHECK else []
        marketplace_str = str(marketplace).strip().lower()
        
        if marketplace_str in skip_list_lower:
            logger.info(f"Skipping stock check for marketplace={marketplace_str} | facility={facility_name} | sku={item.get('sku', 'unknown')}")
            continue
        
        wh_sku = item["wh_sku"]
        total_quantity = item["quantity"] * item["pack_uom_quantity"]
        item_name = item.get("name", "")

        if wh_sku in wh_sku_data:
            wh_sku_data[wh_sku]["quantity"] += total_quantity
            # Add item name to the list if it exists and is not already there
            if item_name and item_name not in wh_sku_data[wh_sku]["names"]:
                wh_sku_data[wh_sku]["names"].append(item_name)
        else:
            wh_sku_data[wh_sku] = {
                "quantity": total_quantity,
                "names": [item_name] if item_name else []
            }

    # Validate aggregated quantities for each unique wh_sku
    for wh_sku, data in wh_sku_data.items():
        # Join item names with commas for error messages
        item_names_str = ", ".join(data["names"]) if data["names"] else None
        stock_validator = StockValidator(facility_name, wh_sku)
        stock_validator.validate_stock(data["quantity"], item_names_str)

    logger.info(f"Stock validated | facility={facility_name} | unique_skus={len(wh_sku_data)}")
