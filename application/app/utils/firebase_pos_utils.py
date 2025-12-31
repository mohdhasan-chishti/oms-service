import firebase_admin
from firebase_admin import firestore
from typing import Optional

from app.logging.utils import get_app_logger
logger = get_app_logger("firebase_pos_utils")

pos_instance = firebase_admin.get_app("pos")

async def get_user_display_name_from_token(user_id: str, phone_number: Optional[str] = None) -> str:
    """
    Get user display name from Firestore using user_id from Firebase token.
    """
    try:
        db = firestore.client(app=pos_instance)
        if phone_number:
            normalized_phone = phone_number if phone_number.startswith('+') else f'+{phone_number}'
            pos_users_ref = db.collection("pos_users").document(normalized_phone)
            pos_user_doc = pos_users_ref.get()
            
            if pos_user_doc.exists:
                pos_user_data = pos_user_doc.to_dict()
                display_name = pos_user_data.get("displayName") or pos_user_data.get("name")
                if display_name and display_name.strip():
                    return display_name.strip()
                else:
                    logger.info(f"No display name found in pos_users for phone: {normalized_phone}")
        else:
            logger.info(f"No phone number found in token for user_id: {user_id}")
        return "POS User"
        
    except Exception as e:
        logger.error(f"Error getting user name for pos_user_id {user_id}: {e}", exc_info=True)
        if phone_number:
            return phone_number
        return "POS User"