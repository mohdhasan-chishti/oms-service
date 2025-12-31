"""
OTP Model
Stores OTP codes for phone number authentication
"""

from sqlalchemy import Column, Integer, String, Boolean, Index
from app.models.common import CommonModel



class StaticOtps(CommonModel):
    """
    Static OTP model - stores static OTP codes for phone authentication testing
    """
    __tablename__ = "static_otps"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(15), nullable=False, index=True)
    otp = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)