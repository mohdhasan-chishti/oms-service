from pydantic import BaseModel
from typing import Optional

class EncryptCustomerCodeRequest(BaseModel):
    customer_code: str

class EncryptCustomerCodeResponse(BaseModel):
    success: bool
    encrypted_customer_code: Optional[str] = None
    iv: Optional[str] = None
    message: str
