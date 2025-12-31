"""
Core constants for the Rozana OMS application

This module contains all the core constants used across the application,
including order status codes, system-wide enums, and other shared values.
"""

class OrderStatus:
    """Order status constants for lifecycle management"""
    
    # Rozana (OMS) statuses
    DRAFT = 0
    OPEN = 10
    FULFILLED = 11
    PARTIALLY_FULFILLED = 12
    UNFULFILLED = 13
    CANCELED = 14
    RETURN = 15
    RETURNED = 17
    CANCELLED_PENDING_REFUND = 16  # Added for pending refund after cancellation
    POTIONS_SYNCED = 18
    POTIONS_SYNC_FAILED = 19

    # WMS statuses
    WMS_SYNCED = 21
    WMS_SYNC_FAILED = 22

    # WMS processing statuses - numerical codes
    WMS_OPEN = 23
    WMS_INPROGRESS = 24
    WMS_PICKED = 25
    WMS_FULFILLED = 26
    WMS_INVOICED = 27
    WMS_CANCELED = 28

    # TMS statuses
    TMS_SYNCED = 31
    TMS_SYNC_FAILED = 32
    RIDER_ASSIGNED = 33
    TMS_OUT_FOR_DELIVERY = 34
    TMS_DELIVERED = 35
    TMS_PARTIAL_DELIVERED = 36
    TMS_RETURNED = 37
    TMS_CANCELLED = 38
    TMS_RTO_REVOKE = 39

    # String representation of statuses used in database
    DB_STATUS_MAP = {
        # OMS statuses
        "oms_draft": DRAFT,
        "oms_open": OPEN,
        "oms_fulfilled": FULFILLED,
        "oms_partial_fulfilled": PARTIALLY_FULFILLED,
        "oms_unfulfilled": UNFULFILLED,
        "oms_canceled": CANCELED,
        "oms_return_initiated": RETURN,
        "oms_returned": RETURNED,
        "oms_potions_synced": POTIONS_SYNCED,
        "oms_potions_sync_failed": POTIONS_SYNC_FAILED,

         # WMS statuses - string to code mapping
        "wms_synced": WMS_SYNCED,
        "wms_sync_failed": WMS_SYNC_FAILED,
        "open" : WMS_OPEN,
        "in_progress": WMS_INPROGRESS,
        "picked": WMS_PICKED,
        "fulfilled": WMS_FULFILLED,
        "invoiced": WMS_INVOICED,

        # TMS statuses
        "tms_synced": TMS_SYNCED,
        "tms_sync_failed": TMS_SYNC_FAILED,
        "rider_assigned": RIDER_ASSIGNED,
        "out_for_delivery": TMS_OUT_FOR_DELIVERY,
        "delivered": TMS_DELIVERED,
    }

    @classmethod
    def get_customer_status_name(cls, status_code: int) -> str:
        """Get customer-friendly status name from status code (only Rozana statuses)"""
        # Only show customer-relevant statuses, hide internal WMS/TMS statuses
        customer_status_map = {
            cls.DRAFT: "Payment Pending",
            cls.OPEN: "Processing",
            cls.FULFILLED: "Delivered", 
            cls.PARTIALLY_FULFILLED: "Delivered",
            cls.UNFULFILLED: "Delivery Failed",
            cls.CANCELED: "Cancelled",
            cls.RETURN: "Return Initiated",
            cls.RETURNED: "Returned",
            cls.CANCELLED_PENDING_REFUND: "Cancelled",
            cls.POTIONS_SYNCED: "Confirmed",
            cls.POTIONS_SYNC_FAILED: "Processing",
            cls.WMS_SYNCED: "Confirmed",
            cls.WMS_SYNC_FAILED: "Processing",
            cls.WMS_OPEN: "Confirmed",
            cls.WMS_CANCELED: "Cancelled",
            cls.WMS_INPROGRESS: "Packing Your Order",
            cls.WMS_PICKED: "Packing Your Order",
            cls.WMS_FULFILLED: "Packed",
            cls.WMS_INVOICED: "Ready For Dispatch",
            cls.TMS_SYNCED: "Finding Rider",
            cls.TMS_SYNC_FAILED: "Ready For Dispatch",
            cls.RIDER_ASSIGNED: "Rider Assigned",
            cls.TMS_OUT_FOR_DELIVERY: "Out For Delivery",
            cls.TMS_DELIVERED: "Delivered",
            cls.TMS_RETURNED: "Delivery Failed",
            cls.TMS_CANCELLED: "Delivery Cancelled",
            cls.TMS_RTO_REVOKE: "Delivery Cancelled",
            cls.TMS_PARTIAL_DELIVERED: "Delivered"
        }
        return customer_status_map.get(status_code, "Processing")
    
    
    @classmethod
    def is_rozana_status(cls, status_code: int) -> bool:
        """Check if status code is a Rozana (OMS) status"""
        return status_code in [cls.OPEN, cls.FULFILLED, cls.PARTIALLY_FULFILLED, cls.UNFULFILLED, cls.CANCELED, cls.POTIONS_SYNCED, cls.POTIONS_SYNC_FAILED]
    
    @classmethod
    def is_wms_status(cls, status_code: int) -> bool:
        """Check if status code is a WMS status"""
        return status_code in [
            cls.WMS_SYNCED, cls.WMS_SYNC_FAILED, cls.WMS_OPEN, cls.WMS_PICKED, cls.WMS_INPROGRESS, cls.WMS_FULFILLED, cls.WMS_INVOICED
        ]

    @classmethod
    def is_tms_status(cls, status_code: int) -> bool:
        """Check if status code is a TMS status"""
        return status_code in [cls.TMS_SYNCED, cls.TMS_SYNC_FAILED]
    



class PaymentStatus:
    """Payment status constants for payment lifecycle management"""
    
    # Payment statuses (integer-based for consistency with OrderStatus)
    PENDING = 50
    COMPLETED = 51
    FAILED = 52
    REFUNDED = 53
    
    # String representation of payment statuses used in database enum
    DB_STATUS_MAP = {
        50 : PENDING,
        51 : COMPLETED,
        52 : FAILED,
        53 : REFUNDED,
    }
    
    # Reverse mapping for database operations
    STATUS_TO_DB_MAP = {
        50: "pending",
        51: "completed",
        52: "failed",
        53: "refunded",
    }
    
    # Status descriptions
    STATUS_DESCRIPTIONS = {
        50: "Payment Pending",
        51: "Payment Completed", 
        52: "Payment Failed",
        53: "Payment Refunded"
    }
    
    @classmethod
    def get_description(cls, status_code: int) -> str:
        """Get human-readable description for payment status"""
        return cls.STATUS_DESCRIPTIONS.get(status_code, f"Unknown Payment Status ({status_code})")
    
    @classmethod
    def is_valid_status(cls, status_code: int) -> bool:
        """Check if status code is a valid payment status"""
        return status_code in [cls.PENDING, cls.COMPLETED, cls.FAILED, cls.REFUNDED]
    
    @classmethod
    def from_db_string(cls, db_status: str) -> int:
        """Convert database string status to integer constant"""
        return cls.DB_STATUS_MAP.get(db_status, cls.PENDING)
    
    @classmethod
    def to_db_string(cls, status_code: int) -> str:
        """Convert integer constant to database string status"""
        return cls.STATUS_TO_DB_MAP.get(status_code, "pending")
    
    @classmethod
    def is_final_status(cls, status_code: int) -> bool:
        """Check if payment status is final (completed, failed, or refunded)"""
        return status_code in [cls.COMPLETED, cls.FAILED, cls.REFUNDED]


class SystemConstants:
    """System-wide constants"""
    
    # Default ETA hours for new orders
    DEFAULT_ETA_HOURS = 24
    
    # Order ID prefix length
    ORDER_ID_PREFIX_LENGTH = 4
    
    # Maximum retry attempts for external service calls
    MAX_RETRY_ATTEMPTS = 3
    
    # Default timeout for external API calls (seconds)
    DEFAULT_API_TIMEOUT = 30


class ReturnTypeConstants:
    """Return type constants for order items"""
    
    # Return type codes
    NOT_RETURN_NOT_EXCHANGE = "00"
    NOT_RETURN_EXCHANGE = "01"
    RETURN_NOT_EXCHANGE = "10"
    RETURN_AND_EXCHANGE = "11"
    
    # Return type descriptions mapping
    RETURN_TYPE_MAP = {
        NOT_RETURN_NOT_EXCHANGE: "not return and not exchange",
        NOT_RETURN_EXCHANGE: "not return and exchange",
        RETURN_NOT_EXCHANGE: "return and not exchange", 
        RETURN_AND_EXCHANGE: "return and exchange"
    }
    
    @classmethod
    def get_description(cls, return_type_code: str) -> str:
        """Get human-readable description for return type code"""
        return cls.RETURN_TYPE_MAP.get(return_type_code, "not return not exchange")


class ReturnReasons:
    """Return reason constants"""
    
    DAMAGED = "DAMAGED"
    WRONG_ITEM = "WRONG_ITEM"
    NOT_AS_DESCRIBED = "NOT_AS_DESCRIBED"
    CHANGED_MIND = "CHANGED_MIND"
    OTHER="OTHER"
    
    REASON_DESCRIPTIONS = {
        DAMAGED: "Item was damaged",
        WRONG_ITEM: "Wrong item received",
        NOT_AS_DESCRIBED: "Item not as described",
        CHANGED_MIND: "Changed my mind",
        OTHER: "Other"
    }
    
    @classmethod
    def get_all_reasons(cls):
        """Get all available return reasons"""
        return [
            {"code": code, "description": desc}
            for code, desc in cls.REASON_DESCRIPTIONS.items()
        ]


class CancelReasons:
    """Cancel reason constants"""
    
    NO_LONGER_NEED = "NO_LONGER_NEED"
    STORE_ASKED_TO_CANCEL = "STORE_ASKED_TO_CANCEL"
    FOUND_BETTER_PRICE = "FOUND_BETTER_PRICE"
    DELIVERY_TIME_TOO_LONG = "DELIVERY_TIME_TOO_LONG"
    DELIVERY_DELAY = "DELIVERY_DELAY"
    ADDRESS_CHANGE = "ADDRESS_CHANGE"
    PAYMENT_ISSUE = "PAYMENT_ISSUE"
    OTHER = "OTHER"
    
    REASON_DESCRIPTIONS = {
        NO_LONGER_NEED: "No longer need the order / Ordered by mistake",
        STORE_ASKED_TO_CANCEL: "Store asked to cancel",
        FOUND_BETTER_PRICE: "Found a better price elsewhere",
        DELIVERY_TIME_TOO_LONG: "Delivery time too long",
        DELIVERY_DELAY: "Not Delivered on Time",
        ADDRESS_CHANGE: "Need to change delivery address",
        PAYMENT_ISSUE: "Payment issues",
        OTHER: "Other"
    }
    
    @classmethod
    def get_all_reasons(cls):
        """Get all available cancel reasons as key-value pairs"""
        return {code: desc for code, desc in cls.REASON_DESCRIPTIONS.items()}


class APIConstants:
    """API-related constants"""
    
    # API version
    API_VERSION = "v1"
    
    # Default page size for paginated responses
    DEFAULT_PAGE_SIZE = 20
    
    # Maximum page size for paginated responses
    MAX_PAGE_SIZE = 100

class RefundStatus:
    """Refund status constants"""
    CREATED = 60
    PENDING = 61
    PROCESSED = 62
    FAILED = 63

    @classmethod
    def get_description(cls, status_code: int) -> str:
        """Get human-readable description of refund status"""
        descriptions = {
            cls.CREATED: "Created",
            cls.PENDING: "Processing",
            cls.PROCESSED: "Processed",
            cls.FAILED: "Failed"
        }
        return descriptions.get(status_code, "Unknown")

class ReturnStatus:
    """Return status constants for return process"""
    RETURN_CREATED = 40
    RTO_INITIATED = 41
    RTO_DELIVERED = 42
    REVERSE_ORDER_ACCEPTED = 43
    REVERSE_PICKUP_COMPLETED = 44
    REVERSE_DELIVERY_COMPLETED = 45
    
    @classmethod
    def get_description(cls, status_code: int) -> str:
        """Get human-readable description of return status"""
        status_descriptions = {
            cls.RETURN_CREATED: "Return Created",
            cls.RTO_INITIATED: "RTO Initiated",
            cls.RTO_DELIVERED: "RTO Delivered",
            cls.REVERSE_ORDER_ACCEPTED: "Reverse Order Accepted",
            cls.REVERSE_PICKUP_COMPLETED: "Reverse Pickup Completed",
            cls.REVERSE_DELIVERY_COMPLETED: "Reverse Delivery Completed"
        }
        return status_descriptions.get(status_code, "Unknown Return Status")


class PromotionOfferType:
    FLAT_DISCOUNT = "flat_discount"
    CASHBACK = "cashback"
    FREEBEE = "freebee"
    COUPON = "coupon"


class PromotionUserFrequency:
    FIRST_ORDER_EVER = "first_order_ever"
    FIRST_ORDER_APP = "first_order_app"
    FIRST_ORDER_POS = "first_order_pos"
    ANY = "any"


class PromotionErrorCode:
    PROMO_NOT_FOUND = "PROMO_NOT_FOUND"
    PROMO_EXPIRED = "PROMO_EXPIRED"
    PROMO_NOT_STARTED = "PROMO_NOT_STARTED"
    FACILITY_MISMATCH = "FACILITY_MISMATCH"
    CHANNEL_NOT_ALLOWED = "CHANNEL_NOT_ALLOWED"
    MIN_PURCHASE_NOT_MET = "MIN_PURCHASE_NOT_MET"
    PAYMENT_METHOD_NOT_ALLOWED = "PAYMENT_METHOD_NOT_ALLOWED"
    NOT_FIRST_PURCHASE = "NOT_FIRST_PURCHASE"
    USER_FREQUENCY_NOT_MET = "USER_FREQUENCY_NOT_MET"
    INVALID_PROMOTION = "INVALID_PROMOTION"
    COUPON_USAGE_LIMIT_REACHED = "COUPON_USAGE_LIMIT_REACHED"
    COUPON_USER_LIMIT_REACHED = "COUPON_USER_LIMIT_REACHED"