"""
Firebase utilities for customer operations
"""
import firebase_admin
from firebase_admin import auth,firestore
from fastapi import HTTPException
from typing import Optional
import re

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

# Get Firebase app instance
app_instance = firebase_admin.get_app("app")

async def get_customer_id_from_phone_number(phone_number: str, origin: str = "app") -> str:
    """
    Get customer ID from phone number using Firebase Auth.
    
    Args:
        phone_number: Phone number to lookup customer (should include country code)
        origin: Order origin - "app" or "pos" (default: "app")
        
    Returns:
        str: Customer ID (Firebase UID)
        
    Raises:
        HTTPException: If customer not found, disabled, or Firebase call fails
    """
    try:
        user_record = auth.get_user_by_phone_number(phone_number, app=app_instance)
        
        # Check if the customer account is disabled (blocks POS orders only)
        if origin == "pos":
            db = firestore.client(app=app_instance)
            user_doc = db.collection("users").document(user_record.uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                if user_data.get("isPosDisabled", False):
                    logger.error(f"Customer account is disabled for phone number: {phone_number}, customer_id: {user_record.uid}")
                    raise HTTPException(status_code=403, detail="Customer account is disabled for POS orders.")
        
        customer_id = user_record.uid
        logger.info(f"Successfully retrieved customer ID: {customer_id} for phone: {phone_number}")
        
        return customer_id
        
    except auth.UserNotFoundError:
        logger.warning(f"Customer not found for phone number: {phone_number}")
        raise HTTPException(status_code=404, detail="Customer not found")
    except ValueError as e:
        logger.warning(f"Invalid phone number format: {phone_number} - {e}")
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Firebase error getting customer for phone {phone_number}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve customer information") from e
