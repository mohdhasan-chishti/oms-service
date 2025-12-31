from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from app.models.common import CommonModel
from app.core.constants import PaymentStatus, RefundStatus

class PaymentDetails(CommonModel):
    """
    Payment details model - simplified to store one payment mode per record
    """
    __tablename__ = "payment_details"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    payment_order_id = Column(String(50), nullable=True)
    payment_id = Column(String(50), nullable=False, index=True)
    payment_amount = Column(DECIMAL(10, 2), nullable=False)
    payment_date = Column(TIMESTAMP(timezone=True), nullable=False)
    payment_mode = Column(String(50), nullable=False)
    payment_status = Column(Integer, nullable=False, default=PaymentStatus.PENDING, comment="Payment status: 50=Pending, 51=Completed, 52=Failed, 53=Refunded")
    terminal_id = Column(String(50), nullable=True, index=True)

    # Add the total_amount field that the database requires
    total_amount = Column(DECIMAL(10, 2), nullable=False, default=0.0)
    remarks = Column(String(50), nullable=True)

    # Relationship back to order
    order = relationship("Order", backref="payments")


    # Payment mode list
    PAYMENT_MODES = ['cash', 'cod', 'razorpay', 'cashfree', 'wallet', 'online']

    def __repr__(self):
        return f"<PaymentDetails(id={self.id}, order_id={self.order_id}, payment_id='{self.payment_id}', status={self.payment_status})>"
    
    def get_status_description(self) -> str:
        """Get human-readable description of payment status"""
        return PaymentStatus.get_description(self.payment_status)
    
    def is_completed(self) -> bool:
        """Check if payment is completed"""
        return self.payment_status == PaymentStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if payment failed"""
        return self.payment_status == PaymentStatus.FAILED
    
    def is_pending(self) -> bool:
        """Check if payment is pending"""
        return self.payment_status == PaymentStatus.PENDING
    
    def is_final_status(self) -> bool:
        """Check if payment has reached a final status"""
        return PaymentStatus.is_final_status(self.payment_status)

class RefundDetails(CommonModel):
    """
    Refund details model for tracking Razorpay refunds
    """
    __tablename__ = "refund_details"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payment_details.id"), nullable=False, index=True)
    refund_id = Column(String(50), nullable=False, unique=True, index=True)
    refund_amount = Column(DECIMAL(10, 2), nullable=False)
    refund_currency = Column(String(6), nullable=False, default="INR", server_default="INR")
    refund_status = Column(Integer, nullable=False, default=RefundStatus.CREATED, server_default=str(RefundStatus.CREATED))
    refund_date = Column(TIMESTAMP(timezone=True), nullable=True)
    speed_requested = Column(String(20), nullable=True)
    speed_processed = Column(String(20), nullable=True)
    receipt = Column(String(100), nullable=True)
    batch_id = Column(String(50), nullable=True)
    acquirer_data = Column(String(500), nullable=True)
    notes = Column(String(1000), nullable=True)

    # Relationship back to payment
    payment = relationship("PaymentDetails", backref="refund_details")

    def __repr__(self):
        return f"<RefundDetails(id={self.id}, refund_id='{self.refund_id}', payment_id='{self.payment_id}', status='{self.refund_status}')>"

    def is_processed(self) -> bool:
        """Check if refund is processed"""
        return self.refund_status == "processed"

    def is_pending(self) -> bool:
        """Check if refund is pending"""
        return self.refund_status == "pending"

    def is_failed(self) -> bool:
        """Check if refund failed"""
        return self.refund_status == "failed"

    # Composite indexes for better query performance
    __table_args__ = (
        Index('idx_refund_details_payment_id_status', 'payment_id', 'refund_status'),
        Index('idx_refund_details_status_created', 'refund_status', 'created_at')
    )


class FacilityPaymentGateway(CommonModel):
    """
    Tracks payment gateway status by facility
    """
    __tablename__ = "facility_payment_gateways"

    id = Column(Integer, primary_key=True, index=True)
    facility_name = Column(String(100), nullable=False)
    payment_gateway = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, server_default='true')

    # Composite unique constraint on facility_name and payment_gateway
    __table_args__ = (
        Index('idx_facility_payment_gateway', 'facility_name', 'payment_gateway', unique=True),
        Index('idx_facility_gateway_active', 'facility_name', 'payment_gateway', 'is_active')
    )

    def __repr__(self):
        return f"<FacilityPaymentGateway(facility_name='{self.facility_name}', gateway='{self.payment_gateway}', is_active={self.is_active})>"