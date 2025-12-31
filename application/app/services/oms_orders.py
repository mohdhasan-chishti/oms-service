from typing import Dict, List
from app.repository.orders import OrdersRepository

class OMSOrderService:
    def get_oms_orders_count(self, user_id: str, clause: tuple = None, params: tuple = None) -> int:
        repo = OrdersRepository()
        return repo.get_oms_orders_count(user_id, clause, params)

    def get_oms_orders(self, user_id: str, page_size: int, page: int, clause: tuple = None, params: tuple = None) -> List[Dict]:
        repo = OrdersRepository()
        return repo.get_oms_orders(user_id, page_size, page, clause, params)

    def get_oms_order_items_by_order_ids(self, order_ids: List[str]) -> Dict:
        repo = OrdersRepository()
        return repo.get_oms_order_items_by_order_ids(order_ids)
