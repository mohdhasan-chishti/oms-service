"""
Default payment behavior configuration.

Defines the initial payment status per payment mode to ensure
consistent creation of payment records across the system.
"""
from app.core.constants import PaymentStatus


class PaymentDefaults:
    """Centralized defaults for payment-related behavior."""

    INITIAL_STATUS_BY_MODE = {
        "cash": PaymentStatus.PENDING,
        "online": PaymentStatus.COMPLETED,
        "cod": PaymentStatus.PENDING,
        "razorpay": PaymentStatus.PENDING,
        "wallet": PaymentStatus.PENDING,
        "paytm": PaymentStatus.PENDING,
        "cashfree": PaymentStatus.PENDING,
    }

    @classmethod
    def initial_status_for_mode(cls, mode: str) -> int:
        """Return initial status for a given payment mode.

        Defaults to PENDING for unknown modes.
        """
        if not mode:
            return PaymentStatus.PENDING
        return cls.INITIAL_STATUS_BY_MODE.get(mode.lower(), PaymentStatus.PENDING)
