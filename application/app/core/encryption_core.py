from fastapi import Request, HTTPException
from app.services.encryption_service import EncryptionService
from app.dto.encryption import EncryptCustomerCodeResponse
import logging

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("app.core.encryption_core")

async def encrypt_customer_code_core(customer_code: str, request: Request) -> EncryptCustomerCodeResponse:
    """
    Core function to encrypt customer code from Firebase authenticated user.
    
    Args:
        customer_code: The customer code to encrypt
        request: FastAPI request object containing user info from Firebase middleware
        
    Returns:
        EncryptCustomerCodeResponse: Response with encrypted customer code and IV
    """
    try:
        # Get user info from Firebase middleware
        user_id = getattr(request.state, "user_id", None)
        phone_number = getattr(request.state, "phone_number", None)
        
        if not user_id:
            logger.warning("No user_id found in request state")
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        logger.info(f"Encrypting customer code for user_id: {user_id}")
        
        # Encrypt the customer code
        encrypted_text, iv = EncryptionService.encrypt_customer_code(customer_code)
        
        logger.info(f"Successfully encrypted customer code for user: {user_id}")
        
        return EncryptCustomerCodeResponse(
            success=True,
            encrypted_customer_code=encrypted_text,
            iv=iv,
            message="Customer code encrypted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error encrypting customer code: {e}")
        return EncryptCustomerCodeResponse(
            success=False,
            message=f"Failed to encrypt customer code: {str(e)}"
        )
