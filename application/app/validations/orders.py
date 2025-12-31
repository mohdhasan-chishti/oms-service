from app.dto.orders import OrderCreate
from fastapi import HTTPException
from app.connections.database import execute_raw_sql_readonly
from app.repository.orders import OrdersRepository
from app.repository.invoices import InvoiceRepository
from app.services.selling_price_service import SellingPriceService
from app.logging.utils import get_app_logger
logger = get_app_logger('order_validations')


class OrderCreateValidator:
    def __init__(self, order: OrderCreate = None, user_id: str = None):
        self.order = order
        self.user_id = user_id

    def validate(self):
        self.validate_user_id_customer_id()
        self.validate_duplicate_sku_items()

    def validate_user_id_customer_id(self):
        if self.user_id != self.order.customer_id:
            logger.error(f"User ID and Customer ID do not match | user_id={self.user_id} customer_id={self.order.customer_id}")
            # raise ValueError("User ID and Customer ID do not match")

    def validate_page_size(self, page_size: int = 20, page: int = 1, max_page_size: int = 100):
        # Validate page starts from 1
        if page < 1:
            logger.warning(f"Page number must be 1 or greater | page={page}")
            raise ValueError("Page number must be 1 or greater")

        # Validate page_size is reasonable
        if page_size < 1:
            logger.warning(f"Page size must be at least 1 | page_size={page_size}")
            raise ValueError("Page size must be at least 1")
        if page_size > max_page_size:
            logger.warning(f"Page size must be at most {max_page_size} | page_size={page_size}")
            raise ValueError(f"Page size must be between 1 and {max_page_size}")

    def validate_pagination_params(self, page_size: int = 20, page: int = 1, total_count: int = 0):
        """Validate pagination parameters including page bounds"""
        self.validate_page_size(page_size, page)

        # Calculate total pages
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        # If we have data but page is too high, adjust to last page
        if total_count > 0 and page > total_pages:
            logger.warning(f"Page {page} exceeds maximum page {total_pages} for {total_count} total items")
            raise ValueError(f"Page {page} exceeds maximum page {total_pages} for {total_count} total items")

        return total_pages

    def validate_items_count(self):
        """Validate that the order has at least one item."""
        if not self.order.items or len(self.order.items) < 1:
            raise HTTPException(status_code=400, detail="Order must contain at least one item")

    def validate_duplicate_sku_items(self):
        sku_list = [item.sku for item in self.order.items]
        duplicates = [sku for sku in sku_list if sku_list.count(sku) > 1]
        if duplicates:
            # Build error message with item names
            duplicate_names = []
            for sku in set(duplicates):
                items_with_sku = [item for item in self.order.items if item.sku == sku]
                duplicate_names.append(items_with_sku[0].name)
            error_msg = f"Duplicate items found: {', '.join(duplicate_names)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def validate_quantity(self, origin: str = "app"):
        if origin == "app":
            # For app orders, quantity should be an integer
            invalid_skus = []
            for item in self.order.items:
                if item.quantity != int(item.quantity):
                    invalid_skus.append(item.sku)
                else:
                    # Normalize to int to avoid downstream float handling for app
                    item.quantity = int(item.quantity)
            
            # If any invalid SKUs found, raise error with all of them
            if invalid_skus:
                sku_list = ', '.join(invalid_skus)
                raise HTTPException(status_code=400, detail=f"For app orders, quantity must be an integer for SKUs: {sku_list}")

    def validate_pos_extra_quantity(self, origin: str = "app"):
        """Ensure pos_extra_quantity is only accepted for POS orders."""
        if origin != "pos" and self.order:
            invalid_skus = [
                item.sku for item in self.order.items
                if getattr(item, "pos_extra_quantity", 0) not in (0, None)
            ]
            if invalid_skus:
                sku_list = ', '.join(invalid_skus)
                raise HTTPException(
                    status_code=400,
                    detail=f"pos_extra_quantity allowed only for POS orders for SKUs: {sku_list}"
                )

    def validate_user_type(self):
        """Validate that user_type is valid (exists in DB or in default mapping)."""
        SellingPriceService.validate_user_type(self.order.user_type)


class OrderUserValidator:
    def __init__(self, order_id: str = None, user_id: str = None):
        self.order_id = order_id
        self.user_id = user_id

    def validate_order_with_user(self):
        query = """SELECT customer_id FROM orders WHERE order_id = :order_id"""
        params = {"order_id": self.order_id}
        result = execute_raw_sql_readonly(query, params)
        if not result:
            repo = OrdersRepository()
            legacy_header = repo.get_legacy_order_by_code(self.order_id)
            if not legacy_header:
                logger.error(f"Order not found in OMS or legacy: {self.order_id}")
                raise HTTPException(status_code=404, detail="Order not found or access denied")
        elif result[0].get('customer_id') != self.user_id:
            logger.error(f"Order {self.order_id} not belongs to customer {self.user_id}")
            raise HTTPException(status_code=404, detail="Order not found or access denied")
        
class OrderFacilityValidator:
    def __init__(self, order_id: str = None, facility_name: str = None):
        self.order_id = order_id
        self.facility_name = facility_name
    
    def validate_order_with_facility(self):
        query = """SELECT facility_name FROM orders WHERE order_id = :order_id"""
        params = {"order_id":self.order_id}
        result = execute_raw_sql_readonly(query, params)
        if not result or result[0].get('facility_name') != self.facility_name:
            raise HTTPException(status_code=404, detail="Order not found or access denied")


class OrderInvoiceValidator:
    def validate_invoice_s3_url_with_order_id(self, invoice_s3_url: str, order_id: str):
        """
        Validate that the given invoice_s3_url belongs to the specified order_id.
        """
        invoice_repo = InvoiceRepository()
        invoices = invoice_repo.get_invoices_by_order_id(order_id)
        for invoice in invoices:
            if invoice.get('invoice_s3_url') == invoice_s3_url:
                return True
        logger.warning(f"Invoice not found for the specified order or invalid invoice URL: {invoice_s3_url}")
        raise ValueError("Invoice not found for the specified order or invalid invoice URL")