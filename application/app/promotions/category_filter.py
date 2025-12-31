from typing import Dict, List, Optional
from decimal import Decimal

# DTOs
from app.dto.cart import CartItem

# Logging
from app.logging.utils import get_app_logger
logger = get_app_logger("app.promotions.category_filter")


class CategoryFilter:
    """Handles category-based filtering for promotions with include/exclude logic"""

    @staticmethod
    def item_matches_categories(item: CartItem, categories: List[str]) -> bool:
        """
        Check if an item matches any of the specified categories at any hierarchy level
        
        Args:
            item: CartItem with category information (should have all 3 levels from UI)
            categories: List of categories to match against (from promotion)
            
        Returns:
            True if item matches any category at any level, False otherwise
        """
        if not categories:
            return True  # No category filter means all items match
            
        # Get all category levels for this item (UI should send all three)
        item_categories = [
            item.category,
            item.sub_category, 
            item.sub_sub_category
        ]
        
        # Remove None/empty values and normalize
        item_categories = [cat.strip() for cat in item_categories if cat is not None and cat.strip()]
        
        # Check if any item category matches any of the target categories (case-insensitive)
        for item_cat in item_categories:
            for target_cat in categories:
                if item_cat.lower() == target_cat.lower():
                    logger.debug(f"Category match found: item_category='{item_cat}' matches target='{target_cat}' for SKU={item.sku}")
                    return True
        
        logger.debug(f"No category match: item_categories={item_categories} vs target_categories={categories} for SKU={item.sku}")
        return False

    @staticmethod
    def filter_items_by_sku(items: List[CartItem], applicable_skus: List[str], excluded_skus: List[str]) -> List[CartItem]:
        """
        Filter items based on SKU include/exclude lists (highest priority)
        
        Args:
            items: List of cart items
            applicable_skus: List of SKUs to include (if specified, only these SKUs are eligible)
            excluded_skus: List of SKUs to exclude
            
        Returns:
            Filtered list of cart items
        """
        filtered_items = []
        
        for item in items:
            # SKU exclusion has highest priority
            if excluded_skus and item.sku in excluded_skus:
                logger.debug(f"Item {item.sku} excluded by SKU exclusion list")
                continue
                
            # If applicable_skus is specified, only include items in that list
            if applicable_skus and item.sku not in applicable_skus:
                logger.debug(f"Item {item.sku} not in applicable SKUs list")
                continue
                
            filtered_items.append(item)
            
        return filtered_items

    @staticmethod
    def filter_items_by_categories(items: List[CartItem], applicable_categories: List[str], excluded_categories: List[str]) -> List[CartItem]:
        """
        Filter items based on category include/exclude lists with proper precedence
        
        Args:
            items: List of cart items
            applicable_categories: List of categories to include (if specified, only items in these categories are eligible)
            excluded_categories: List of categories to exclude
            
        Returns:
            Filtered list of cart items
        """
        filtered_items = []
        
        for item in items:
            # Step 1: Apply include filter first
            if applicable_categories:
                if not CategoryFilter.item_matches_categories(item, applicable_categories):
                    logger.debug(f"Item {item.sku} not in applicable categories: categories={[item.category, item.sub_category, item.sub_sub_category]}")
                    continue
                    
            # Step 2: Apply exclude filter (exclude takes precedence)
            if excluded_categories:
                if CategoryFilter.item_matches_categories(item, excluded_categories):
                    logger.debug(f"Item {item.sku} excluded by category exclusion: categories={[item.category, item.sub_category, item.sub_sub_category]}")
                    continue
                
            filtered_items.append(item)
            
        return filtered_items

    @staticmethod
    def get_eligible_items(items: List[CartItem], promotion_doc: Dict) -> List[CartItem]:
        """
        Get eligible items based on promotion filters with proper priority
        
        Priority order:
        1. SKU filters (applicable_skus, excluded_skus) - highest priority
        2. Category filters (included_categories, excluded_categories)
        
        Args:
            items: List of cart items
            promotion_doc: Promotion document with filter criteria
            
        Returns:
            List of eligible cart items
        """
        # Extract filter criteria from promotion
        applicable_skus = promotion_doc.get("applicable_skus", [])
        excluded_skus = promotion_doc.get("excluded_skus", [])
        applicable_categories = promotion_doc.get("applicable_categories", [])
        excluded_categories = promotion_doc.get("excluded_categories", [])
        
        logger.info(f"Filtering items | total_items={len(items)} applicable_skus={len(applicable_skus)} excluded_skus={len(excluded_skus)} applicable_categories={len(applicable_categories)} excluded_categories={len(excluded_categories)}")
        
        # Step 1: Apply SKU filters (highest priority)
        if applicable_skus or excluded_skus:
            eligible_items = CategoryFilter.filter_items_by_sku(items, applicable_skus, excluded_skus)
            logger.info(f"After SKU filtering: {len(eligible_items)} items")
            
            # If SKU filters are applied, still apply category exclusions but not inclusions
            if excluded_categories:
                eligible_items = CategoryFilter.filter_items_by_categories(eligible_items, [], excluded_categories)
                logger.info(f"After category exclusion filtering: {len(eligible_items)} items")
        else:
            # Step 2: Apply category filters (only if no SKU filters are specified)
            eligible_items = CategoryFilter.filter_items_by_categories(items, applicable_categories, excluded_categories)
            logger.info(f"After category filtering: {len(eligible_items)} items")
        
        return eligible_items

    @staticmethod
    def calculate_eligible_cart_value(eligible_items: List[CartItem]) -> Decimal:
        """
        Calculate total cart value for eligible items
        
        Args:
            eligible_items: List of eligible cart items
            
        Returns:
            Total value of eligible items
        """
        total_value = Decimal("0")
        
        for item in eligible_items:
            item_total = item.sale_price * item.quantity
            total_value += item_total
            
        logger.info(f"Eligible cart value calculated: {total_value} from {len(eligible_items)} items")
        return total_value

    @staticmethod
    def validate_promotion_eligibility(items: List[CartItem], promotion_doc: Dict) -> Dict:
        """
        Validate if promotion is eligible based on cart items and return eligibility details
        
        Args:
            items: List of cart items
            promotion_doc: Promotion document
            
        Returns:
            Dictionary with eligibility details
        """
        eligible_items = CategoryFilter.get_eligible_items(items, promotion_doc)
        eligible_cart_value = CategoryFilter.calculate_eligible_cart_value(eligible_items)
        min_purchase = Decimal(str(promotion_doc.get("min_purchase", 0)))
        
        is_eligible = len(eligible_items) > 0 and eligible_cart_value >= min_purchase
        
        return {
            "is_eligible": is_eligible,
            "eligible_items": eligible_items,
            "eligible_cart_value": eligible_cart_value,
            "min_purchase": min_purchase,
            "eligible_items_count": len(eligible_items),
            "total_items_count": len(items)
        }
