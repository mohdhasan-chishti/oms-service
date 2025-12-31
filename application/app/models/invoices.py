"""
SQLAlchemy ORM Models
These models define the database schema using SQLAlchemy ORM.
Use these for internal/small queries that benefit from ORM features.
"""

from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, ForeignKey, Computed, Index, Enum, Boolean
from sqlalchemy.orm import relationship
from app.models.common import CommonModel

class InvoiceDetails(CommonModel):
    """
    Invoice Details
    """
    __tablename__ = "invoice_details"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(128), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    invoice_s3_url = Column(String(2048), nullable=True)
    raven_link = Column(String(2048), nullable=True)


    # Relationship back to order
    order = relationship("Order", backref="invoice_details")


    def __repr__(self):
        return f"<InvoiceDetails(id={self.id}, invoice_number='{self.invoice_number}', order_id='{self.order_id}')"

    # Composite indexes for better query performance
    __table_args__ = (
        Index('idx_invoice_details_invoice_number', 'invoice_number'),
    )
