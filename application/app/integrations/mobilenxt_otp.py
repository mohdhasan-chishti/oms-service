import requests
from urllib.parse import urlencode
from typing import Dict
from app.logging.utils import get_app_logger
from app.config.settings import OMSConfigs

logger = get_app_logger(__name__)
configs = OMSConfigs()


class MobileNXTOTPAction:
    """
    MobileNXT OTP integration for sending SMS messages.
    Simple wrapper around MobileNXT API.
    """

    BASE_URL = "https://api.mobilnxt.in/api/push"
    SENDER_ID = "RZANA"

    def __init__(self):
        """Initialize with MobileNXT credentials from config."""
        self.access_key = configs.MOBILENXT_ACCESS_KEY
        self.tid = configs.MOBILENXT_TID
        self.app_signature = configs.APP_SIGNATURE

        if not self.access_key or not self.tid:
            logger.error("MobileNXT credentials not configured")
            raise ValueError("MobileNXT credentials not configured")

    async def send_otp_sms(self, phone_number: str, otp_code: str, app_signature: str) -> Dict:
        """
        Send OTP via SMS using MobileNXT API.
        
        Args:
            phone_number: Recipient's phone number
            otp_code: OTP code to send
            app_signature: App signature for verification
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        otp_code = str(otp_code) + " " + app_signature
        try:
            message = f"Your OTP for rozana.in is {otp_code}"

            data = {
                'accesskey': self.access_key,
                'tid': self.tid,
                'to': phone_number,
                'text': message,
                'from': self.SENDER_ID,
                'unicode': '0'
            }

            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            response = requests.post(
                self.BASE_URL,
                headers=headers,
                data=urlencode(data),
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"OTP SMS sent successfully to {phone_number}")
                return {'success': True, 'message': 'OTP sent successfully'}
            else:
                user_message = response.json().get('message', 'Failed to send OTP') if response.text else 'Failed to send OTP'
                logger.warning(f"Failed to send OTP SMS. Status: {response.status_code}, Response: {response.text}")
                return {'success': False, 'message': user_message}

        except requests.RequestException as e:
            logger.error(f"Request failed while sending OTP SMS to {phone_number}: {str(e)}")
            return {'success': False, 'message': 'Failed to connect to OTP service'}
        except Exception as e:
            logger.error(f"Error sending OTP SMS to {phone_number}: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'An error occurred while sending OTP'}
