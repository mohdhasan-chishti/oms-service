"""
Selling Price Mapping Model
Maps selling prices to different user types
"""

from sqlalchemy import Column, Integer, String, Boolean, Index
from app.models.common import CommonModel


class SellingPriceMapping(CommonModel):
    """
    Selling Price Mapping model - maps selling prices to different user types
    """
    __tablename__ = "sellingpricemapping"

    id = Column(Integer, primary_key=True, index=True)
    selling_price_key = Column(String(255), nullable=False, index=True)
    user_type = Column(String(100), nullable=False, index=True)
    status = Column(Boolean, nullable=False, default=True, server_default="true")

    def __repr__(self):
        return f"<SellingPriceMapping(id={self.id}, selling_price_key='{self.selling_price_key}', user_type='{self.user_type}', status={self.status})>"

    # Composite indexes for better query performance
    __table_args__ = (
        Index('idx_selling_price_mapping_key_type', 'selling_price_key', 'user_type'),
        Index('idx_selling_price_mapping_status', 'status'),
        Index('idx_selling_price_mapping_created', 'created_at'),
    )
