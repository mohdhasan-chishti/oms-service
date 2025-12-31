import time
from typing import Dict, List
from decimal import Decimal
from app.core.constants import PromotionErrorCode
from app.logging.utils import get_app_logger
logger = get_app_logger("app.promotions_validator")


class PromotionValidator:
    def __init__(self, promotion_doc: Dict, order_data: Dict, suppress_error_logs: bool = False, usage: str = "calculate"):
        self.doc = promotion_doc
        self.order = order_data
        self.errors = []
        self.suppress_error_logs = suppress_error_logs
        self.usage = usage

    def validate_time_window(self):
        now_ts = int(time.time())
        start_date = self.doc.get("start_date", 0)
        end_date = self.doc.get("end_date", 0)

        if now_ts < start_date:
            self.errors.append({"code": PromotionErrorCode.PROMO_NOT_STARTED, "field": "start_date", "message": "Promotion has not started yet"})
        elif now_ts > end_date:
            if not self.suppress_error_logs:
                logger.error(f"Promotion expired | now={now_ts} end_date={end_date}")
            self.errors.append({"code": PromotionErrorCode.PROMO_EXPIRED, "field": "end_date", "message": "Promotion has expired"})
    
    def validate_facility(self):
        doc_facility = self.doc.get("facility_code", "")
        order_facility = self.order.get("facility_name", "")
        if doc_facility and doc_facility != order_facility:
            if not self.suppress_error_logs:
                logger.error(f"Facility mismatch | doc_facility={doc_facility} order_facility={order_facility}")
            self.errors.append({"code": PromotionErrorCode.FACILITY_MISMATCH, "field": "facility_code", "message": f"Promotion not valid for facility {order_facility}"})
    
    def validate_channel(self, channel: str):
        discount_at = self.doc.get("discount_at", [])
        if discount_at and channel not in discount_at:
            if not self.suppress_error_logs:
                logger.error(f"Channel not allowed | channel={channel} discount_at={discount_at}")
            self.errors.append({"code": PromotionErrorCode.CHANNEL_NOT_ALLOWED, "field": "discount_at", "message": f"Promotion not valid for channel {channel}"})
    
    def validate_min_purchase(self):
        min_purchase = Decimal(str(self.doc.get("min_purchase", 0)))
        discount_amount = Decimal(str(self.doc.get("discount_amount", 0)))
        offer_type = self.doc.get("offer_type", "")
        order_amount = Decimal(str(self.order.get("total_amount", 0)))

        if offer_type != "cashback":
            amount_check = order_amount
            if self.usage == "order_creation":
                amount_check = order_amount + discount_amount

            if amount_check < min_purchase:
                if not self.suppress_error_logs:
                    logger.error(f"Minimum purchase not met | min_purchase={min_purchase} order_amount={order_amount}")
                self.errors.append({"code": PromotionErrorCode.MIN_PURCHASE_NOT_MET, "field": "total_amount", "message": f"Minimum purchase ₹{min_purchase} not met", "details": {"required": float(min_purchase), "provided": float(order_amount)}})
        else:
            if order_amount < min_purchase:
                if not self.suppress_error_logs:
                    logger.error(f"Minimum purchase not met for coupon | min_purchase={min_purchase} order_amount={order_amount}")
                self.errors.append({"code": PromotionErrorCode.MIN_PURCHASE_NOT_MET, "field": "total_amount", "message": f"Minimum purchase ₹{min_purchase} not met for coupon", "details": {"required": float(min_purchase), "provided": float(order_amount)}})  

    def validate_payment_method(self, payment_modes: List[str]):
        allowed_methods = self.doc.get("payment_methods", [])
        if allowed_methods:
            valid = any(pm in allowed_methods for pm in payment_modes)
            if not valid:
                if not self.suppress_error_logs:
                    logger.error(f"Payment method not allowed | payment_modes={payment_modes} allowed_methods={allowed_methods}")
                self.errors.append({"code": PromotionErrorCode.PAYMENT_METHOD_NOT_ALLOWED, "field": "payment_method", "message": f"Payment method not allowed for this promotion"})

    def validate_all(self, channel: str, payment_modes: List[str]):
        self.validate_time_window()
        self.validate_facility()
        self.validate_channel(channel)
        self.validate_min_purchase()
        self.validate_payment_method(payment_modes)
        return self.errors
