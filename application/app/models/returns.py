from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.models.common import CommonModel
from app.core.constants import ReturnStatus

class Returns(CommonModel):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True, index=True)
    return_reference = Column(String(50), unique=True, nullable=False, index=True)
    sale_return_id = Column(String(50), nullable=False, server_default="")
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    customer_id = Column(String(50), nullable=False, index=True)
    return_type = Column(String(10), nullable=False)  
    return_reason = Column(String(100), nullable=True)
    comments = Column(Text, nullable=True)
    return_method = Column(String(20), nullable=False, default='api')
    status = Column(String(20), nullable=False, default='approved', index=True) 
    return_status = Column(Integer, nullable=False, default=ReturnStatus.RETURN_CREATED,server_default="40")
    total_refund_amount = Column(DECIMAL(10, 2), nullable=True)
    refund_mode = Column(String(20), nullable=True)  # 'cash' or 'wallet'
    refund_status = Column(String(20), nullable=False, default='pending')
    approved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)

    order = relationship("Order", backref="return_requests")
    return_items = relationship("ReturnItem", back_populates="returns", cascade="all, delete-orphan")
    return_images = relationship("ReturnImage", back_populates="returns", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Returns(id={self.id}, return_reference='{self.return_reference}', order_id={self.order_id}, status='{self.status}')>"

    __table_args__ = (
        Index('idx_returns_customer_status', 'customer_id', 'status'),
        Index('idx_returns_created_at', 'created_at'),
    )


class ReturnItem(CommonModel):
    __tablename__ = "return_items"

    id = Column(Integer, primary_key=True, index=True)
    return_id = Column(Integer, ForeignKey("returns.id"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False, index=True)
    sku = Column(String(100), nullable=False, index=True)
    quantity_returned = Column(DECIMAL(10, 3), nullable=False, default=0, server_default="0")
    accepted_quantity = Column(DECIMAL(10, 3), nullable=False, default=0, server_default="0")
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    sale_price = Column(DECIMAL(10, 2), nullable=False)
    refund_amount = Column(DECIMAL(10, 2), nullable=True)
    return_reason = Column(Text, nullable=True)
    item_condition = Column(String(20), nullable=True) 
    condition_notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default='approved')
    return_status = Column(Integer, nullable=False, default=ReturnStatus.RETURN_CREATED, server_default="40")

    returns = relationship("Returns", back_populates="return_items")
    order_item = relationship("OrderItem", backref="return_items")
    return_images = relationship("ReturnImage", back_populates="return_item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ReturnItem(id={self.id}, return_id={self.return_id}, sku='{self.sku}', quantity={self.quantity_returned})>"


class ReturnImage(CommonModel):
    __tablename__ = "return_images"

    id = Column(Integer, primary_key=True, index=True)
    return_id = Column(Integer, ForeignKey("returns.id"), nullable=False, index=True)
    return_item_id = Column(Integer, ForeignKey("return_items.id"), nullable=True, index=True)
    image = Column(String(500), nullable=False)

    returns = relationship("Returns", back_populates="return_images")    
    return_item = relationship("ReturnItem", back_populates="return_images")

    def __repr__(self):
        return f"<ReturnImage(id={self.id}, return_id={self.return_id}, image='{self.image}')>"
