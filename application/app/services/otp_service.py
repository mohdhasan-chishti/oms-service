import random
import hashlib
from typing import Dict, Optional
from app.logging.utils import get_app_logger
from app.config.settings import OMSConfigs
from app.connections.redis_wrapper import RedisJSONWrapper
from app.repository.otp import OTPRepository

logger = get_app_logger(__name__)
configs = OMSConfigs()


class OTPService:
    """
    Simple OTP service focused on core logic:
    - OTP generation
    - OTP hashing and storage
    - OTP validation
    """

    CACHE_PREFIX = "auth_otp_"

    def __init__(self):
        """Initialize OTP service with configuration."""
        self.otp_length = configs.MOBILENXT_OTP_LENGTH
        self.otp_expiry = configs.MOBILENXT_OTP_EXPIRY

    def generate_otp(self) -> str:
        """
        Generate a random numeric OTP.
        
        Returns:
            str: Random OTP of configured length
        """
        return str(random.randint(10 ** (self.otp_length - 1), (10 ** self.otp_length) - 1))

    def hash_otp(self, otp: str) -> str:
        """
        Hash OTP using SHA256.
        
        Args:
            otp: OTP code to hash
            
        Returns:
            str: Hashed OTP
        """
        return hashlib.sha256(otp.encode()).hexdigest()

    def get_cache_key(self, phone_number: str) -> str:
        """
        Get Redis cache key for OTP storage.
        
        Args:
            phone_number: Phone number
            
        Returns:
            str: Cache key
        """
        return f"{self.CACHE_PREFIX}{phone_number}"

    def _get_redis_client(self) -> Optional[RedisJSONWrapper]:
        """
        Get Redis client for OTP storage.
        
        Returns:
            RedisJSONWrapper: Redis client or None if unavailable
        """
        try:
            redis_client = RedisJSONWrapper(database=configs.REDIS_CACHE_DB)
            if getattr(redis_client, "connected", False):
                return redis_client
            else:
                logger.error("Redis connection failed for OTP storage")
                return None
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {str(e)}")
            return None

    async def store_otp(self, phone_number: str, otp: str) -> bool:
        """
        Store hashed OTP in Redis.
        
        Args:
            phone_number: Phone number
            otp: OTP code to store
            
        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.error("Redis client unavailable for OTP storage")
                return False

            hashed_otp = self.hash_otp(otp)
            cache_key = self.get_cache_key(phone_number)
            redis_client.set_with_ttl(cache_key, hashed_otp, self.otp_expiry)
            logger.info(f"OTP stored for {phone_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to store OTP for {phone_number}: {str(e)}")
            return False

    async def validate_otp(self, phone_number: str, otp_code: str) -> Dict:
        """
        Validate OTP against stored hashed value.
        
        Args:
            phone_number: Phone number
            otp_code: OTP code to validate
            
        Returns:
            dict: {
                'valid': bool,
                'message': str
            }
        """
        try:
            if not otp_code or not str(otp_code).isdigit():
                logger.warning(f"Invalid OTP format for {phone_number}")
                return {'valid': False, 'message': 'Invalid OTP format'}

            # Check if this is a test credential
            otp_repo = OTPRepository()
            test_credentials = otp_repo.get_test_credentials()
            if phone_number in test_credentials:
                expected_otp = test_credentials[phone_number]
                if str(otp_code) == expected_otp:
                    logger.info(f"Test OTP validated successfully for {phone_number}")
                    return {'valid': True, 'message': 'OTP valid', 'is_test': True}
                else:
                    logger.warning(f"Invalid test OTP provided for {phone_number}")
                    return {'valid': False, 'message': 'Invalid OTP'}

            redis_client = self._get_redis_client()
            if not redis_client:
                logger.error("Redis client unavailable for OTP validation")
                return {'valid': False, 'message': 'OTP validation service unavailable'}

            cache_key = self.get_cache_key(phone_number)
            stored_hashed_otp = redis_client.get(cache_key)

            if not stored_hashed_otp:
                logger.warning(f"OTP expired or not found for {phone_number}")
                return {'valid': False, 'message': 'OTP expired or not found'}

            provided_hashed_otp = self.hash_otp(otp_code)
            if stored_hashed_otp == provided_hashed_otp:
                try:
                    redis_client.delete(cache_key)
                except Exception as e:
                    logger.warning(f"Failed to delete OTP from Redis: {str(e)}")

                logger.info(f"OTP validated successfully for {phone_number}")
                return {'valid': True, 'message': 'OTP valid'}
            else:
                logger.warning(f"Invalid OTP provided for {phone_number}")
                return {'valid': False, 'message': 'Invalid OTP'}

        except Exception as e:
            logger.error(f"Error validating OTP for {phone_number}: {str(e)}", exc_info=True)
            return {'valid': False, 'message': 'An error occurred while validating OTP'}
