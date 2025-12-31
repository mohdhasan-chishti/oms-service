"""
SQLAlchemy ORM Models
These models define the database schema using SQLAlchemy ORM.
Use these for internal/small queries that benefit from ORM features.
"""

from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, ForeignKey, Computed, Index, Enum, Boolean, Text, text
from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, ForeignKey, Computed, Index, Enum, Boolean, Text, text
from sqlalchemy.orm import relationship
from app.models.common import CommonModel
from sqlalchemy.sql import text

class Order(CommonModel):
    """
    Order model using SQLAlchemy ORM.
    Maps to the orders table created in the migration.
    """
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    random_prefix = Column(String(4), nullable=False)
    order_id = Column(String(50), Computed("random_prefix || id::TEXT", persisted=True), unique=True, nullable=False, index=True)
    customer_id = Column(String(50), nullable=False, index=True)
    customer_name = Column(String(100), nullable=False)
    facility_id = Column(String(50), nullable=False, index=True)
    facility_name = Column(String(100), nullable=False)
    status = Column(Integer, nullable=False, default=10, index=True)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    eta = Column(TIMESTAMP(timezone=True), nullable=True)
    order_mode = Column(String(20), Enum('web', 'app', 'pos', name='order_mode_enum'), nullable=False)
    is_approved = Column(Boolean, nullable=False, default=False)
    handling_charge = Column(DECIMAL(10, 2), nullable=False, default=0.00, server_default="0.00")
    surge_charge = Column(DECIMAL(10, 2), nullable=False, default=0.00, server_default="0.00")
    delivery_charge = Column(DECIMAL(10, 2), nullable=False, default=0.00, server_default="0.00")
    packaging_charge = Column(DECIMAL(10, 2), nullable=False, default=0.00, server_default="0.00")
    invoice_key = Column(String(1024), nullable=True)
    biller_id = Column(String(50), nullable=True)
    biller_name = Column(String(30), nullable=True)
    remarks = Column(String(255), nullable=True, default="", server_default=text("''"))
    updated_by = Column(String(255), nullable=False, default="", server_default=text("''"))
    promotion_code = Column(String(50), nullable=True, default="", server_default=text("''"))
    promotion_type = Column(String(32), nullable=True, default="", server_default=text("''"))
    promotion_discount = Column(DECIMAL(10, 2), nullable=False, default=0.00, server_default="0.00")
    user_type = Column(String(100), nullable=False, default="customer", server_default="customer", index=True)
    marketplace = Column(String(32), nullable=False, default="ROZANA", server_default="ROZANA")
    referral_id = Column(String(32), nullable=False, default="", server_default=text("''"))
    cancel_reason = Column(String(100), nullable=False, default="", server_default=text("''"))
    cancel_remarks = Column(String(255), nullable=False, default="", server_default=text("''"))
    parent_order_id = Column(String(50), nullable=True)
    domain_name = Column(String(32), nullable=False, default="", server_default=text("''"))
    provider_id = Column(String(128), nullable=False, default="", server_default=text("''"))
    location_id = Column(String(128), nullable=False, default="", server_default=text("''"))


    def __repr__(self):
        return f"<Order(id={self.id}, order_id='{self.order_id}', customer_id='{self.customer_id}', status={self.status})>"

    # Composite indexes for better query performance
    __table_args__ = (
        Index('idx_orders_customer_status', 'customer_id', 'status'),
        Index('idx_orders_facility_status', 'facility_id', 'status'),
        Index('idx_orders_status_created', 'status', 'created_at'),
    )



# Additional models can be added here as the schema grows
# For example:

class OrderItem(CommonModel):
    """
    Order items model - for future use when order items table is added
    """
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    sku = Column(String(100), nullable=False, index=True)
    typesense_id = Column(String(100), nullable=False, default="", server_default=text("''"))
    name = Column(String(200), nullable=True)  # Optional name field
    quantity = Column(DECIMAL(10, 3), nullable=False)
    fulfilled_quantity = Column(DECIMAL(10, 3), default=0, server_default="0")
    unfulfilled_quantity = Column(DECIMAL(10, 3), default=0, server_default="0")
    delivered_quantity = Column(DECIMAL(10, 3), default=0, server_default="0")
    cancelled_quantity = Column(DECIMAL(10, 3), default=0, server_default="0")
    refunded_quantity = Column(DECIMAL(10, 3), default=0, server_default="0")
    pos_extra_quantity = Column(DECIMAL(10, 3), default=0, server_default="0")
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    sale_price = Column(DECIMAL(10, 2), nullable=False)
    original_sale_price = Column(DECIMAL(10, 2), nullable=True)
    status = Column(Integer, nullable=False, default=10)
    pack_uom_quantity = Column(Integer, nullable=False, default=1)
    wh_sku = Column(String(255))
    thumbnail_url = Column(Text, nullable=True)
    remarks = Column(String(255), nullable=True, default="", server_default=text("''"))
    updated_by = Column(String(255), nullable=False, default="", server_default=text("''"))
    hsn_code = Column(String(10), nullable=False, default="", server_default=text("''"))
    category = Column(String(255), nullable=False, default="", server_default=text("''"))
    sub_category = Column(String(255), nullable=False, default="", server_default=text("''"))
    sub_sub_category = Column(String(255), nullable=False, default="", server_default=text("''"))
    brand_name = Column(String(255), nullable=False, default="", server_default=text("''"))
    marketplace = Column(String(32), nullable=False, default="ROZANA", server_default="ROZANA")
    referral_id = Column(String(32), nullable=False, default="", server_default=text("''"))
    domain_name = Column(String(32), nullable=False, default="", server_default=text("''"))
    provider_id = Column(String(128), nullable=False, default="", server_default=text("''"))
    location_id = Column(String(128), nullable=False, default="", server_default=text("''"))
    

    # Tax fields
    cgst = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    sgst = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    igst = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    cess = Column(DECIMAL(10, 2), nullable=False, default=0.00)

    # Return policy fields
    is_returnable = Column(Boolean, nullable=False, default=False)
    return_type = Column(String(2), nullable=False, default='00')
    return_window = Column(Integer, nullable=False, default=0)

    # Selling price net field
    selling_price_net = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    cod_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00, server_default="0.00")

    # Relationship back to order
    order = relationship("Order", backref="items")

    def __repr__(self):
        return f"<OrderItem(id={self.id}, order_id='{self.order_id}', sku='{self.sku}', quantity={self.quantity})>"

    # Composite indexes for better query performance
    __table_args__ = (
        Index('idx_order_items_order_sku', 'order_id', 'sku'),
        Index('idx_order_items_sku_status', 'sku', 'status'),
        Index('idx_order_items_order_status', 'order_id', 'status'),
    )



class OrderAddress(CommonModel):
    """
    Order address model - for future use when order addresses table is added
    """
    __tablename__ = "order_addresses"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    phone_number = Column(String(20), nullable=False)
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(100), nullable=False, default="india")
    type_of_address = Column(String(20), nullable=False)
    longitude = Column(DECIMAL(10, 7), nullable=True)
    latitude = Column(DECIMAL(10, 7), nullable=True)

    # Relationship back to order
    order = relationship("Order", backref="addresses")

    def __repr__(self):
        return f"<OrderAddress(id={self.id}, order_id='{self.order_id}', type='{self.type_of_address}')>"

    # Composite indexes for better query performance
    __table_args__ = (
        Index('idx_order_addresses_order_type', 'order_id', 'type_of_address'),
        Index('idx_order_addresses_city_state', 'city', 'state'),
        Index('idx_order_addresses_postal_country', 'postal_code', 'country'),
        Index('idx_order_addresses_coordinates', 'longitude', 'latitude'),
    )



class OrderMeta(CommonModel):
    """
    Order metadata model to capture request context like IP, device, and user agent.
    """
    __tablename__ = "order_metadata"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    client_ip = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    device = Column(String(128), nullable=True)
    platform = Column(String(128), nullable=True)
    version = Column(String(64), nullable=True)
    longitude = Column(DECIMAL(10, 7), nullable=False, default=0.00, server_default="0.00")
    latitude = Column(DECIMAL(10, 7), nullable=False, default=0.00, server_default="0.00")

    # Relationship back to order
    order = relationship("Order", backref="metadata_entries")

    __table_args__ = (
        Index('idx_order_metadata_order_id', 'order_id'),
    )

