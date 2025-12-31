import firebase_admin
from firebase_admin import auth, firestore
from fastapi import APIRouter, HTTPException, status
from app.dto.auth_otp import RequestOTPRequest, RequestOTPResponse, ValidateOTPRequest, ValidateOTPResponse
from app.repository.otp import OTPRepository
from app.services.otp_service import OTPService
from app.integrations.mobilenxt_otp import MobileNXTOTPAction
from app.logging.utils import get_app_logger
from app.utils.datetime_helpers import get_ist_now

from app.config.settings import OMSConfigs
configs = OMSConfigs()

logger = get_app_logger(__name__)
app_instance = firebase_admin.get_app("app")
pos_instance = firebase_admin.get_app("pos")

router = APIRouter(tags=["auth"])

def _create_user_in_firestore(user, phone_number, firebase_instance):
    """Create a user document in Firestore after Firebase Auth user creation."""
    try:
        db = firestore.client(app=firebase_instance)
        user_data = {
            "createdAt": get_ist_now().isoformat(),
            "displayName": user.display_name or "Customer",
            "email": "",
            "isProfileComplete": True,
            "phoneNumber": user.phone_number,
            "uid": user.uid,
            "updatedAt": get_ist_now().isoformat(),
            "userType": "customer"
        }
        # Create nested structure: users/{userId}/profile/data
        db.collection("users").document(user.uid).collection("profile").document("data").set(user_data)
        logger.info(f"User document created in Firestore at users/{user.uid}/profile/data for phone: {phone_number}")
    except Exception as firestore_error:
        logger.error(f"Failed to create user in Firestore: {firestore_error}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user account")


@router.post("/request-otp", response_model=RequestOTPResponse)
async def request_otp(request: RequestOTPRequest):
    """
    Request OTP for the given phone number.
    Steps:
    1. Validate phone number
    2. Validate app signature if provided
    3. Generate OTP using OTPService
    4. Send OTP via MobileNXT integration
    5. Store hashed OTP in Redis
    """
    try:
        phone_number = request.phone_number.strip()
        app_signature = configs.APP_SIGNATURE
        if request.app_signature:
            app_signature = request.app_signature.strip()

        logger.info(f"OTP request received with app_signature for phone: {phone_number}")

        otp_service = OTPService()

        # Check if this is a test credential
        otp_repo = OTPRepository()
        test_credentials = otp_repo.get_test_credentials()
        if phone_number in test_credentials:
            stored = await otp_service.store_otp(phone_number, test_credentials[phone_number])
            if not stored:
                logger.error(f"Failed to store OTP for {phone_number}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store OTP")
            return RequestOTPResponse(
                success=True,
                 message="OTP sent successfully", 
                 phone_number=phone_number,
                  otp_id=phone_number
            )

        mobilenxt_action = MobileNXTOTPAction()

        otp = otp_service.generate_otp()
        logger.info(f"Generated OTP for {phone_number}")

        sms_result = await mobilenxt_action.send_otp_sms(phone_number, otp, app_signature)
        if not sms_result['success']:
            logger.warning(f"Failed to send OTP SMS: {sms_result['message']}")
            message = "Invalid phone number format" if 'format' in sms_result.get('message', '').lower() else "Failed to send OTP"
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        stored = await otp_service.store_otp(phone_number, otp)
        if not stored:
            logger.error(f"Failed to store OTP for {phone_number}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store OTP")

        logger.info(f"OTP request successful for phone: {phone_number}")
        return RequestOTPResponse(success=True, message="OTP sent successfully", phone_number=phone_number, otp_id=phone_number)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in request_otp: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP")


@router.post("/validate-otp", response_model=ValidateOTPResponse)
async def validate_otp(request: ValidateOTPRequest):
    """
    Validate OTP and generate Firebase custom token.
    Steps:
    1. Validate inputs
    2. Validate OTP using OTPService
    3. Get user from Firebase
    4. Create Firebase custom token
    5. Return token to UI
    """
    try:
        phone_number = request.phone_number.strip()
        otp_code = request.otp_code.strip()
        username = request.username.strip() if request.username else "customer"
        otp_service = OTPService()
        validation_result = await otp_service.validate_otp(phone_number, otp_code)

        if not validation_result['valid']:
            logger.warning(f"OTP validation failed for {phone_number}: {validation_result['message']}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=validation_result['message'])

        channel = request.channel
        firebase_instance = app_instance
        if channel == "pos":
            firebase_instance = pos_instance

        try:
            user_record = auth.get_user_by_phone_number(phone_number, app=firebase_instance)
            logger.info(f"User found for {phone_number}: {user_record.uid}")
            
            if channel == "app":
                # Ensure customer profile exists in Firestore
                db = firestore.client(app=firebase_instance)
                doc_ref = db.collection("users").document(user_record.uid).collection("profile").document("data")
                if not doc_ref.get().exists:
                    _create_user_in_firestore(user_record, phone_number, firebase_instance)
        except auth.UserNotFoundError:
            logger.info(f"User not found for phone number {phone_number}, creating new user")

            if channel == "app":
                # Create new user in Firebase Auth
                try:
                    user_record = auth.create_user(phone_number=phone_number, display_name=username, app=firebase_instance)
                    logger.info(f"New user created with UID: {user_record.uid} for phone: {phone_number}")

                    # Also create user document in Firestore
                    _create_user_in_firestore(user_record, phone_number, firebase_instance)

                except Exception as create_error:
                    logger.error(f"Failed to create user for {phone_number}: {str(create_error)}", exc_info=True)
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user account")
            
            elif channel == "pos":
                # Check if user exists in Firestore pos_users collection first
                db = firestore.client(app=firebase_instance, database_id=configs.FIRESTORE_DATABASE)
                pos_user_doc = db.collection("pos_users").document(phone_number).get()
                
                if not pos_user_doc.exists:
                    logger.info(f"POS user not found in Firestore for {phone_number}")
                    return ValidateOTPResponse(success=True, message="Biller Not Found", phone_number=phone_number)
                
                # User exists in Firestore, create in Firebase Auth
                try:
                    user_record = auth.create_user(phone_number=phone_number, display_name=username, app=firebase_instance)
                    logger.info(f"New POS user created with UID: {user_record.uid} for phone: {phone_number}")

                except Exception as create_error:
                    logger.error(f"Failed to create user for {phone_number}: {str(create_error)}", exc_info=True)
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user account")
            else:
                logger.error(f"Invalid channel: {channel}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel")
        try:
            custom_token = auth.create_custom_token(user_record.uid, app=firebase_instance)
            token_str = custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token
            logger.info(f"Custom token generated for user {user_record.uid}")
        except Exception as e:
            logger.error(f"Error generating custom token for {phone_number}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate authentication token")

        logger.info(f"OTP validation successful for phone: {phone_number}, user: {user_record.uid}")
        return ValidateOTPResponse(success=True, message="OTP verified successfully", phone_number=phone_number, user_id=user_record.uid, custom_token=token_str)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in validate_otp: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate OTP")
