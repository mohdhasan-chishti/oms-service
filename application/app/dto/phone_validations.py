from pydantic import BaseModel, field_validator
import re

from app.logging.utils import get_app_logger
logger = get_app_logger('phone_number_validations')

class PhoneNumberValidator(BaseModel):
    phone_number: str
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if not v:
            logger.error(f"Incorrect phone number")
            raise ValueError('Incorrect Phone number')
        
        # Remove non-digits except +
        cleaned = re.sub(r'[^\d+]', '', v)
        
        # Validate and normalize to +91XXXXXXXXXX format
        if re.match(r'^\d{10}$', cleaned):
            return f'+91{cleaned}'
        elif re.match(r'^91\d{10}$', cleaned):
            return f'+{cleaned}'
        elif re.match(r'^\+91\d{10}$', cleaned):
            return cleaned
        elif re.match(r'^0\d{10}$', cleaned):
            return f'+91{cleaned[1:]}'
        logger.error(f"Invalid phone number format: {v}")
        raise ValueError('Invalid phone number format. Expected: 10 digits, 91+10 digits, or +91+10 digits')


def validate_phone_number(phone: str) -> str:
    return PhoneNumberValidator(phone_number=phone).phone_number