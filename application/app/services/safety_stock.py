from app.connections.redis_wrapper import RedisJSONWrapper
from app.logging.utils import get_app_logger

logger = get_app_logger("safety_stock")


class SafetyStockConfigManager:
    """
    Manages category-level safety stock configuration from Redis.

    Priority order (highest to lowest):
    1. sub_sub_category (safetystock:<sub_sub_category>)
    2. sub_category (safetystock:<sub_category>)
    3. category (safetystock:<category>)
    4. Environment default (fallback)
    """

    def __init__(self, default_quantity: float):
        """
        Initialize SafetyStockConfigManager.
        Args:
            default_quantity: Default safety stock quantity from environment
        """
        self.redis_wrapper = RedisJSONWrapper()
        self.default_quantity = default_quantity

    def get_safety_stock(self, categories: dict) -> float:
        """
        Resolve safety stock based on category hierarchy with priority.
        Args:
            categories: Dict with keys 'category', 'sub_category', 'sub_sub_category'

        Returns:
            Safety stock value based on priority order
        """
        # Priority 1: Check sub_sub_category
        if categories.get("sub_sub_category"):
            safety_stock = self._get_safety_stock_from_redis(categories["sub_sub_category"])
            if safety_stock is not None:
                logger.info(f"SAFETY_STOCK_CONFIG: Using sub_sub_category config - sub_sub_category='{categories['sub_sub_category']}', safety_stock={safety_stock}")
                return safety_stock

        # Priority 2: Check sub_category
        if categories.get("sub_category"):
            safety_stock = self._get_safety_stock_from_redis(categories["sub_category"])
            if safety_stock is not None:
                logger.info(f"SAFETY_STOCK_CONFIG: Using sub_category config - sub_category='{categories['sub_category']}', safety_stock={safety_stock}")
                return safety_stock

        # Priority 3: Check category
        if categories.get("category"):
            safety_stock = self._get_safety_stock_from_redis(categories["category"])
            if safety_stock is not None:
                logger.info(f"SAFETY_STOCK_CONFIG: Using category config - category='{categories['category']}', safety_stock={safety_stock}")
                return safety_stock

        # Priority 4: Use environment default
        logger.info(f"SAFETY_STOCK_CONFIG: No category-level config found, using environment default - safety_stock={self.default_quantity}")
        return self.default_quantity

    def _get_safety_stock_from_redis(self, category_value: str) -> float:
        """
        Retrieve safety stock value from Redis for a given category.
        Args:
            category_value: Category value to look up

        Returns:
            Safety stock value if found, None otherwise
        """
        key = f"safetystock:{category_value}"
        try:
            val = self.redis_wrapper.get(key)
            if val is None:
                return None

            # Handle both string and numeric values
            if isinstance(val, (int, float)):
                return float(val)

            return float(val)
        except (ValueError, TypeError) as e:
            logger.error(f"SAFETY_STOCK_CONFIG: Error parsing safety stock value for key '{key}': {e}")
            return None
        except Exception as e:
            logger.error(f"SAFETY_STOCK_CONFIG: Error retrieving safety stock from Redis for key '{key}': {e}")
            return None
