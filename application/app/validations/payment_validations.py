from app.dto.orders import OrderCreate

from app.logging.utils import get_app_logger
logger = get_app_logger('payment_validations')

class PaymentValidator:
    def __init__(self, order: OrderCreate = None):
        self.order = order

    def validate_payment_mode_by_origin(self, origin: str):
        """Validate all payment modes based on origin (app/pos)."""
        # Payment object is now mandatory, so we can directly access it
        payment_modes = [p.payment_mode.lower() for p in self.order.payment]

        # Check if user_type is distributor - restrict COD for distributors
        user_type = getattr(self.order, 'user_type', '').lower()
        if user_type == 'distributor':
            for mode in payment_modes:
                if mode == 'cod':
                    logger.error(f"COD payment not allowed for distributor user type")
                    raise ValueError("COD payment mode is not allowed for distributors")

        if origin == "app":
            # App origin: allow cashfree, cod, razorpay, wallet
            allowed = {"cod", "razorpay", "wallet", "cashfree"}
            for mode in payment_modes:
                if mode not in allowed:
                    logger.error(f"Invalid payment_mode for app origin: {mode}")
                    raise ValueError(f"For app origin, payment_mode must be one of: {', '.join(allowed)}. Got: {mode}")
        elif origin == "pos":
            # POS origin: allow cash-like payments, wallet, and paytm_pos
            allowed = {"cash", "wallet", "online", "paytm_pos"}
            for mode in payment_modes:
                if mode not in allowed:
                    logger.error(f"Invalid payment_mode for pos origin: {mode}")
                    raise ValueError(f"For pos origin, payment_mode must be one of: {', '.join(allowed)}. Got: {mode}")
        # For other origins, no specific restrictions (or add as needed)

    def validate_create_payment_order(self, origin: str):
        """Validate create_payment_order for each payment dict."""
        for payment in self.order.payment:
            # Wallet must always have create_payment_order=True
            if payment.payment_mode.lower() == "wallet" and not payment.create_payment_order:
                logger.error(f"create_payment_order must be true for wallet payments")
                raise ValueError("For wallet payments, create_payment_order must be true")
            if not payment.create_payment_order:
                continue
            if origin not in ["app", "pos"]:
                logger.error(f"create_payment_order is only valid for 'app' or 'pos' origins. Got: {origin}")
                raise ValueError(f"create_payment_order is only valid for 'app' or 'pos' origins. Got: {origin}")
            valid_modes = {"razorpay", "wallet", "cashfree", "paytm_pos"}
            if payment.payment_mode.lower() not in valid_modes:
                logger.error(f"create_payment_order is only valid for payment modes: {valid_modes}. Got: {payment.payment_mode}")
                raise ValueError(
                    f"create_payment_order is only valid for payment modes: {', '.join(valid_modes)}. "
                    f"Got: {payment.payment_mode}"
                )

    def validate_terminal_id_for_paytm_pos(self):
        """Validate terminal_id is provided when payment_mode is paytm_pos"""
        for payment in self.order.payment:
            if payment.payment_mode.lower() == "paytm_pos":
                if not payment.terminal_id or payment.terminal_id.strip() == "":
                    logger.error(f"terminal_id is required for paytm_pos payment mode")
                    raise ValueError("terminal_id is required when payment_mode is 'paytm_pos'")

    def validate_payment_amounts(self):
        """Validate that payment amounts match the total order amount."""
        if not self.order.payment:
            return
            
        total_payment_amount = 0
        for payment in self.order.payment:
            if payment.amount is None:
                logger.error(f"Payment amount is required for payment mode: {payment.payment_mode}")
                raise ValueError(f"Payment amount is required for payment mode: {payment.payment_mode}")
            total_payment_amount += payment.amount
        
        # Check if payment amounts sum equals total_amount
        if abs(total_payment_amount - self.order.total_amount) > 0.01:  # Allow small floating point differences
            logger.warning(f"Payment amounts sum ({total_payment_amount}) does not match order total amount ({self.order.total_amount})")
            raise ValueError(
                f"Payment amounts sum ({total_payment_amount}) does not match order total amount ({self.order.total_amount})"
            )

    def validate_payment_combinations(self, origin: str):
        """Validate payment combinations to prevent duplicates and ensure valid combinations."""
        if not self.order.payment:
            return
            
        # Count each payment mode
        payment_mode_counts = {}
        for payment in self.order.payment:
            mode = payment.payment_mode.lower()
            payment_mode_counts[mode] = payment_mode_counts.get(mode, 0) + 1
        
        # Check for duplicate payment modes
        for mode, count in payment_mode_counts.items():
            if count > 1:
                logger.error(f"Duplicate payment mode '{mode}' found. Each payment mode can only appear once.")
                raise ValueError(f"Duplicate payment mode '{mode}' found. Each payment mode can only appear once.")
        
        # Validate payment mode combinations
        payment_modes = set(payment_mode_counts.keys())
        
        # Check if user_type is distributor - restrict any COD combinations
        user_type = getattr(self.order, 'user_type', '').lower()
        if user_type == 'distributor' and 'cod' in payment_modes:
            logger.error(f"COD payment combinations not allowed for distributor user type")
            raise ValueError("COD payment mode combinations are not allowed for distributors")
        
        # Check for invalid combinations based on origin
        if origin == "app":
            # App origin: allow razorpay + wallet, cod + wallet, cashfree + wallet, or single payment modes
            if len(payment_modes) > 2:
                logger.error(f"App origin: Maximum 2 payment modes allowed. Found: {payment_modes}")
                raise ValueError("App origin: Maximum 2 payment modes allowed.")
            elif len(payment_modes) == 2:
                valid_combinations = [{"razorpay", "wallet"}, {"cod", "wallet"}, {"cashfree", "wallet"}]
                if payment_modes not in valid_combinations:
                    logger.error(f"App origin: Invalid payment combination: {payment_modes}")
                    raise ValueError("App origin: Only 'razorpay' + 'wallet', 'cod' + 'wallet', or 'cashfree' + 'wallet' combinations are allowed.")
            # Single payment mode is always valid for app
        elif origin == "pos":
            if "paytm_pos" in payment_modes and "online" in payment_modes:
                logger.error(f"POS origin: paytm_pos and online cannot be combined")
                raise ValueError("POS origin: paytm_pos and online payment modes cannot be used together.")
        else:
            # Default validation for other origins
            if len(payment_modes) == 1:
                # Single payment mode is valid
                pass
            else:
                logger.error(f"Invalid payment combination: {payment_modes}")
                raise ValueError("Invalid payment combination. Allowed: single payment mode or 'cash/online' + 'razorpay' combination.")

    def validate_payment_configuration(self, origin: str):
        """Comprehensive validation for payment configuration based on origin"""
        self.validate_payment_mode_by_origin(origin)
        self.validate_create_payment_order(origin)
        self.validate_terminal_id_for_paytm_pos()
        self.validate_payment_combinations(origin)
        self.validate_payment_amounts()
