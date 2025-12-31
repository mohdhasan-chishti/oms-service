from typing import Dict, List, Optional
from app.repository.orders import OrdersRepository


class LegacyOrderService:
    
    def count_legacy_orders(self, user_id: str, clause: tuple = None, params: tuple = None) -> int:
        repo = OrdersRepository()
        return repo.count_legacy_orders(int(user_id)) if user_id is not None else 0

    def get_user_id_by_phone(self, phone_number: str) -> Optional[int]:
        repo = OrdersRepository()
        return repo.get_legacy_user_id_by_phone(phone_number)

    def get_legacy_orders(self, user_id: str, page_size: int, page: int, clause: tuple = None, params: tuple = None) -> List[Dict]:
        repo = OrdersRepository()
        return repo.get_legacy_orders(int(user_id), page_size, page)

    def get_legacy_order_items_by_order_ids(self, order_ids: List[str]) -> Dict:
        repo = OrdersRepository()
        ids = [int(x) for x in order_ids] if order_ids else []
        return repo.get_legacy_order_items_by_order_ids(ids)

    def count_legacy_orders_by_phone(self, phone_number: str) -> int:
        repo = OrdersRepository()
        return repo.count_legacy_orders_by_phone(phone_number)

    def get_legacy_orders_by_phone(self, phone_number: str, page_size: int, page: int) -> List[Dict]:
        repo = OrdersRepository()
        return repo.get_legacy_orders_by_phone(phone_number, page_size, page)
