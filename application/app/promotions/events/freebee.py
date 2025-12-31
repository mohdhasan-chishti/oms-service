from decimal import Decimal
from typing import Dict, List
from app.logging.utils import get_app_logger

logger = get_app_logger("app.promotions.events.freebee")


def compute(promotion_doc: Dict, order_amount: Decimal) -> Decimal:
    """
    Compute discount for freebee promotions.
    For freebee promotions, the discount is typically minimal (like ₹1) 
    as the main benefit is the free items.
    
    Args:
        promotion_doc: Promotion document containing freebee details
        order_amount: Order total amount
        
    Returns:
        Discount amount (usually minimal for freebees)
    """
    logger.info(f"freebee_compute | promotion_doc={promotion_doc} order_amount={order_amount}")
    
    # For freebee promotions, return the discount_amount from promotion doc
    # This is usually a small amount like ₹1
    discount_amount = Decimal(str(promotion_doc.get("discount_amount", 0)))
    
    logger.info(f"freebee_discount_calculated | discount_amount={discount_amount}")
    return discount_amount


def get_freebees(promotion_doc: Dict) -> List[Dict]:
    """
    Extract freebee items from promotion document.
    
    Args:
        promotion_doc: Promotion document containing freebees array
        
    Returns:
        List of freebee items with child_sku and selling_price
    """
    freebees = promotion_doc.get("freebees", [])
    
    if not freebees:
        logger.warning("No freebees found in promotion document")
        return []
    
    # Validate and format freebee items
    formatted_freebees = []
    for freebee in freebees:
        if "child_sku" in freebee and "selling_price" in freebee:
            formatted_freebee = {
                "child_sku": freebee["child_sku"],
                "selling_price": Decimal(str(freebee["selling_price"])),
                "wh_sku": freebee.get("wh_sku")
            }
            formatted_freebees.append(formatted_freebee)
        else:
            logger.warning(f"Invalid freebee item format: {freebee}")
    
    logger.info(f"freebees_extracted | count={len(formatted_freebees)} freebees={formatted_freebees}")
    return formatted_freebees
