import os
import logging
from typing import Dict, List, Tuple
from app.services.typesense_service import TypesenseService
from app.services.selling_price_service import SellingPriceService
from app.dto.orders import OrderItemCreate
from app.core.constants import PromotionOfferType

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

PRICE_CHECK_ENABLED = configs.PRICE_CHECK_ENABLED

class TypesenseValidator:
    def __init__(self, user_type: str = "customer"):
        self.typesense_service = TypesenseService()
        self.user_type = user_type

    async def validate_wh_sku_and_pack_uom_quantity(self, product: Dict, item_name: str = "Product") -> bool:
        wh_sku = product.get("wh_sku")
        pack_uom_quantity = product.get("pack_uom_qty")
        facility_name = product.get("facility_code")
        sku = product.get("child_sku")

        if not wh_sku or not pack_uom_quantity:
            logger.error(f"wh_sku or pack_uom_qty not available for facility {facility_name} and sku {sku}")
            raise ValueError(f"{item_name} is not serviceable")

    async def validate_product_price(self, product: Dict, payload_price: float, item_name: str = "Product") -> bool:
        # check if PRICE_CHECK_ENABLED is enabled
        if not PRICE_CHECK_ENABLED:
            return True

        facility_name = product.get("facility_code")
        sku = product.get("child_sku")

        # Get the price field key for this user type
        price_field = SellingPriceService.get_price_field_for_user_type(self.user_type)
        typesense_price = product.get(price_field) or product.get("selling_price")

        if not typesense_price:
            logger.error(f"No price found in Typesense for SKU {sku} and facility {facility_name}")
            raise ValueError(f"Price information not available for {item_name}")

        # validate price format
        try:
            typesense_price = float(typesense_price)
        except (ValueError, TypeError):
            logger.error(f"Invalid price format in Typesense for SKU {sku} and facility {facility_name}")
            raise ValueError(f"Invalid price data for {item_name}")

        # validate price value
        price_match = abs(payload_price - typesense_price) < 0.01
        if not price_match:
            logger.error(f"Price mismatch for SKU {sku} and facility {facility_name} user_type {self.user_type} payload_price {payload_price} typesense_price {typesense_price}")
            raise ValueError(f"{item_name} price has changed, please refresh and try again")

        return price_match

    async def validate_freebie_eligibility(self, sku: str, facility_name: str, order_amount: float, item_name: str = "Product") -> bool:
        """Validate if order amount meets freebie minimum requirement"""
        try:
            freebie = await self.typesense_service.get_freebie_by_sku(sku, facility_name)
            if not freebie:
                logger.error(f"Freebie item {sku} not found for facility {facility_name}")
                raise ValueError(f"{item_name} is not available as a free item")
            
            freebie_min_amount = float(freebie.get("amount", 0))
            
            if order_amount < freebie_min_amount:
                logger.error(f"Order amount {order_amount} is less than required amount {freebie_min_amount} for freebie {sku}")
                raise ValueError(f"Minimum order of ₹{freebie_min_amount} required to get {item_name} for free")
            
            # Check if freebie is currently active (optional date validation)
            import time
            current_time = int(time.time())
            start_date = freebie.get("start_date")
            end_date = freebie.get("end_date")
            
            if start_date and current_time < start_date:
                logger.error(f"Freebie {sku} is not yet active (starts at {start_date})")
                raise ValueError(f"Offer for free {item_name} has not started yet")
            
            if end_date and current_time > end_date:
                logger.error(f"Freebie {sku} has expired (ended at {end_date})")
                raise ValueError(f"Offer for free {item_name} has expired")
            
            # Check available quantity
            available_qty = freebie.get("available_qty", 0)
            if available_qty <= 0:
                logger.error(f"Freebie {sku} is out of stock")
                raise ValueError(f"Free {item_name} is currently out of stock")
            
            logger.info(f"Freebie {sku} validation passed for order amount {order_amount}")
            return freebie
            
        except Exception as e:
            logger.error(f"Error validating freebie {sku}: {str(e)}", exc_info=True)
            raise e

    def categorize_items(self, items: List[OrderItemCreate]) -> Tuple[List[OrderItemCreate], List[OrderItemCreate], List[OrderItemCreate]]:
        """Categorize items into regular, freebie, and promotion freebee items."""
        regular_items = []
        freebie_items = []
        promotion_freebee_items = []

        for item in items:
            is_freebie = item.sale_price == 0.0
            is_promotion_freebee = getattr(item, 'is_freebee', False)
            if is_promotion_freebee:
                promotion_freebee_items.append(item)
            elif is_freebie:
                freebie_items.append(item)
            else:
                regular_items.append(item)

        return regular_items, freebie_items, promotion_freebee_items

    async def process_regular_items(self, regular_items: List[OrderItemCreate], facility_name: str, origin: str, promotion_type: str, errors: List[str], products: Dict[str, Dict]) -> None:
        """Process and validate regular items."""
        if not regular_items:
            return

        # Include typesense_id (from item.id) in the tuple if available
        sku_data_pairs = [(item.sku, item.unit_price, getattr(item, 'id', None), item.original_sale_price ) for item in regular_items]
        try:
            price_field = SellingPriceService.get_price_field_for_user_type(self.user_type)
            fetched_products = await self.typesense_service.get_products_by_skus(sku_data_pairs, facility_name, origin=origin, price_field=price_field)

            for item in regular_items:
                try:
                    product = fetched_products.get(item.sku)
                    item_name = item.name
                    if not product:
                        errors.append(f"{item_name} is currently unavailable")
                        continue

                    # Validate each item
                    await self.validate_wh_sku_and_pack_uom_quantity(product, item_name)
                    
                    # Validate price based on promotion type
                    if promotion_type in [PromotionOfferType.FLAT_DISCOUNT, PromotionOfferType.COUPON]:
                        price_to_validate = item.original_sale_price
                    else:
                        price_to_validate = item.sale_price
                    await self.validate_product_price(product, price_to_validate, item_name)
                    
                    products[item.sku] = product
                except Exception as e:
                    errors.append(str(e))

        except Exception as e:
            logger.error(f"validation failed: {str(e)}")
            errors.append(f"validation failed: {str(e)}")

    async def process_promotion_freebee_items(self, promotion_freebee_items: List[OrderItemCreate], facility_name: str,errors: List[str],products: Dict[str, Dict]) -> None:
        """Process and validate promotion freebee items individually."""
        for item in promotion_freebee_items:
            try:
                product = await self.typesense_service.get_freebie_by_sku(item.sku, facility_name)
                if not product:
                    errors.append(f"{item.name} is currently unavailable")
                    continue

                # Validate other required fields but skip price validation
                await self.validate_wh_sku_and_pack_uom_quantity(product, item.name)
                products[item.sku] = product
            except Exception as e:
                errors.append(str(e))

    async def process_freebie_items(self, freebie_items: List[OrderItemCreate], facility_name: str,order_amount: float,errors: List[str],products: Dict[str, Dict]) -> None:
        """Process and validate freebie items individually."""
        for item in freebie_items:
            try:
                if not facility_name or order_amount is None:
                    errors.append(f"Unable to validate free {item.name}")
                    continue

                # Validate freebie eligibility
                product = await self.validate_freebie_eligibility(item.sku, facility_name, order_amount, item.name)

                if not product:
                    errors.append(f"{item.name} is currently unavailable")
                    continue

                # Skip price validation for freebie items but validate other fields
                await self.validate_wh_sku_and_pack_uom_quantity(product, item.name)
                products[item.sku] = product
            except Exception as e:
                errors.append(str(e))

    async def validate_items(self, items: List[OrderItemCreate], facility_name: str, order_amount: float = None, origin: str = "app", promotion_type: str = "cashback") -> Tuple[List[str], Dict[str, Dict]]:
        """Validate all items and collect errors. Returns products dict and errors list."""
        errors = []
        products = {}

        regular_items, freebie_items, promotion_freebee_items = self.categorize_items(items)

        # Process each category
        await self.process_regular_items(regular_items, facility_name, origin, promotion_type, errors, products)
        await self.process_promotion_freebee_items(promotion_freebee_items, facility_name, errors, products)
        await self.process_freebie_items(freebie_items, facility_name, order_amount, errors, products)

        return products, errors

    async def enrich_items(self, items: List[OrderItemCreate],  products: Dict[str, Dict], facility_name: str,) -> List[Dict]:
        enriched_items = []
        errors = []
        for item in items:
            try:
                product = products.get(item.sku)
                if not product:
                    logger.error(f"Product {item.sku} Not Found for facility {facility_name}")
                    raise ValueError(f"{item.name} is currently unavailable")

                # Extract only required fields from product
                product_fields = self.typesense_service.extract_item_fields(product)
                enriched_item = {
                    "sku": item.sku,
                    "name": item.name,
                    "typesense_id": item.id,
                    "quantity": item.quantity,
                    "pos_extra_quantity": getattr(item, "pos_extra_quantity", 0),
                    "unit_price": item.unit_price,
                    "sale_price": item.sale_price,
                    "original_sale_price": item.original_sale_price,
                    "category": item.category,
                    "sub_category": item.sub_category,
                    "sub_sub_category": item.sub_sub_category,
                    "is_freebee": getattr(item, "is_freebee", False),
                    "marketplace": getattr(item, "marketplace", "ROZANA"),
                    "referral_id": getattr(item, "referral_id", ""),
                    "domain_name": product_fields.get("domain_name", ""),
                    "provider_id": product_fields.get("provider_id", ""),
                    "location_id": product_fields.get("location_id", ""),
                    **product_fields
                }
                enriched_items.append(enriched_item)
            except Exception as e:
                logger.error(f"Error enriching item {item.sku}: {str(e)}", exc_info=True)
                errors.append(str(e))
        return enriched_items, errors

