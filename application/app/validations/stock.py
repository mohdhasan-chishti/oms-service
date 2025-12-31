from app.connections.redis_wrapper import RedisJSONWrapper, RedisKeyProcessor
from app.services.safety_stock import SafetyStockConfigManager
from app.config.settings import OMSConfigs

from app.logging.utils import get_app_logger
logger = get_app_logger('stock_validations')

configs = OMSConfigs()

class StockValidator:
    def __init__(self, warehouse: str, sku: str):
        self.warehouse = warehouse
        self.sku = sku
        self.redis_key_processor = RedisKeyProcessor()
        self.redis_key = self.redis_key_processor._stock_key(self.warehouse, self.sku)
        self.safety_stock_manager = SafetyStockConfigManager(configs.SAFETY_QUANTITY)

    def get_full_stock(self):
        redis_wrapper = RedisJSONWrapper()
        stock = redis_wrapper.get(self.redis_key)
        if stock is None:
            logger.warning(f"Stock not found for facility {self.warehouse} and sku {self.sku}")
            return None
        return stock

    def get_stock(self):
        full_stock = self.get_full_stock()
        if full_stock is None:
            return {"available_quantity": 0}
        return full_stock["data"]

    def validate_stock(self, quantity: int=1, item_name: str = "Product"):
        stock_data = self.get_stock()
        if stock_data is None:
            logger.error(f"Stock not found for facility {self.warehouse} and sku {self.sku}")
            raise ValueError(f"{item_name} is currently out of stock")

        available_stock = stock_data.get("available_quantity", 0)
        if available_stock < quantity:
            logger.error(f"Stock not available for facility {self.warehouse} and sku {self.sku}")
            raise ValueError(f"Insufficient stock for {item_name} reduce quantity to {available_stock} and try again")
        return True

    def block_stock(self, quantity: int):
        stock = self.get_full_stock()
        if stock is None:
            logger.error(f"Stock not found for facility {self.warehouse} and sku {self.sku}")
            raise ValueError(f"Stock not found for facility {self.warehouse} and sku {self.sku}")

        available_stock = stock["data"].get("available_quantity", 0)
        if available_stock < quantity:
            logger.warning(f"Not enough stock available for facility {self.warehouse} and sku {self.sku}")
            raise ValueError(f"Not enough stock available for facility {self.warehouse} and sku {self.sku}")

        new_available_stock = available_stock - quantity
        stock["data"]["available_quantity"] = new_available_stock
        redis_wrapper = RedisJSONWrapper()
        redis_wrapper.set(self.redis_key, stock)
        return new_available_stock
