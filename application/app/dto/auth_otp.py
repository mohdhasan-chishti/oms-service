from pydantic import BaseModel, Field, field_validator
from typing import Optional
from app.dto.phone_validations import validate_phone_number


class RequestOTPRequest(BaseModel):
    """Request model for requesting OTP"""
    phone_number: str = Field(..., description="Phone number with country code (e.g., 919876543210)")
    app_signature: Optional[str] = Field(None, description="App signature for verification (optional)")
    channel: Optional[str] = Field("app", description="Channel for OTP request (optional)")

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        """Validate and normalize phone number"""
        return validate_phone_number(v)

    
    @field_validator('channel')
    @classmethod
    def validate_channel(cls, v):
        """Validate channel"""
        if v not in ["app", "pos"]:
            raise ValueError("Invalid channel")
        return v


class RequestOTPResponse(BaseModel):
    """Response model for OTP request"""
    success: bool
    message: str
    phone_number: str
    otp_id: Optional[str] = Field(None, description="OTP request ID from Gupshup")


class ValidateOTPRequest(BaseModel):
    """Request model for validating OTP"""
    phone_number: str = Field(..., description="Phone number with country code")
    otp_code: str = Field(..., description="6-digit OTP code")
    channel: Optional[str] = Field("app", description="Channel for OTP request (optional)")
    username: Optional[str] = Field(None, description="Username for Firebase user creation (optional)")

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        """Validate and normalize phone number"""
        return validate_phone_number(v)

    @field_validator('channel')
    @classmethod
    def validate_channel(cls, v):
        """Validate channel"""
        if v not in ["app", "pos"]:
            raise ValueError("Invalid channel")
        return v


class ValidateOTPResponse(BaseModel):
    """Response model for OTP validation"""
    success: bool
    message: str
    phone_number: str
    custom_token: Optional[str] = Field(None, description="Firebase custom token for UI initialization")
    user_id: Optional[str] = Field(None, description="Firebase user ID")
