"""
Facility Configuration Model

Generic facility configuration table for storing key-value pairs with type information.
"""

from sqlalchemy import Column, Integer, String, Index
from app.models.common import CommonModel


class FacilityConfiguration(CommonModel):
    """
    Generic facility configuration table for storing key-value pairs with type information.
    
    Attributes:
        facility_name: Name or identifier of the facility
        config_key: Configuration key (string identifier)
        config_value: Configuration value stored as string
        config_value_type: Data type of the config_value ('int', 'float', 'decimal', 'string')
        config_type: Configuration type/category (string)
    """
    __tablename__ = "facility_configurations"

    id = Column(Integer, primary_key=True, index=True)
    facility_name = Column(String(255), nullable=False, index=True)
    config_key = Column(String(255), nullable=False, index=True)
    config_value = Column(String(1000), nullable=False)  # Allow longer values
    config_value_type = Column(String(50), nullable=False)  # 'int', 'float', 'decimal', 'string'
    config_type = Column(String(255), nullable=False)  # Configuration type/category

    # Composite index for facility + config_key lookup
    __table_args__ = (
        Index("idx_facility_config", "facility_name", "config_key", unique=True),
    )

    def __repr__(self):
        return f"<FacilityConfiguration(facility={self.facility_name}, key={self.config_key}, type={self.config_value_type})>"