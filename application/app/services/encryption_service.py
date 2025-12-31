import base64
import os

# Crypto
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger('app.services.encryption_service')

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

ENCRYPTION_KEY_STR = configs.ENCRYPTION_KEY
IV_KEY_SIZE = 16
ENCRYPTION_KEY = ENCRYPTION_KEY_STR.encode('utf-8')[:IV_KEY_SIZE].ljust(IV_KEY_SIZE, b'\0')

class EncryptionService:
    """Service for AES encryption using CBC mode with PKCS7 padding."""

    @staticmethod
    def generate_initialization_vector(length: int = IV_KEY_SIZE) -> str:
        """Generate initialization vector as hex string (matching your standalone script)."""
        return os.urandom(length).hex()[:length]

    @staticmethod
    def encrypt(plaintext: str, key: str, iv: str) -> str:
        """
        Encrypt plaintext using AES-128 in CBC mode.
        Args:
            plaintext: Text to encrypt
            key: Encryption key as string
            iv: Initialization vector as hex string
        """
        try:
            key_bytes = key.encode("utf-8")
            iv_bytes = iv.encode("utf-8")

            cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
            return base64.b64encode(ciphertext).decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption exception in encrypt(): {e}", exc_info=True)
            raise Exception("Failed to encrypt plaintext")

    @staticmethod
    def decrypt(iv: str, key: str, cipher_text_b64: str) -> str:
        """
        Decrypt ciphertext using AES-128 in CBC mode.
        Args:
            iv: Initialization vector as hex string
            key: Encryption key as string
            cipher_text_b64: Base64 encoded ciphertext
        """
        try:
            key_bytes = key.encode("utf-8")
            iv_bytes = iv.encode("utf-8")
            ciphertext = base64.b64decode(cipher_text_b64)

            cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
            return plaintext.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption exception in decrypt(): {e}", exc_info=True)
            raise Exception("Failed to decrypt ciphertext")

    @staticmethod
    def encrypt_customer_code(customer_code: str) -> tuple[str, str]:
        """
        Encrypt customer code and return encrypted text with IV.
        Returns:
            tuple: (encrypted_text, iv_hex)
        """
        try:
            # Use the encryption key as string (matching your standalone script)
            key = ENCRYPTION_KEY_STR[:IV_KEY_SIZE].ljust(IV_KEY_SIZE, '\0')

            # Generate initialization vector (matching your standalone script method)
            iv = EncryptionService.generate_initialization_vector(IV_KEY_SIZE)

            # Encrypt customer code
            encrypted_text = EncryptionService.encrypt(customer_code, key, iv)

            logger.info(f"Successfully encrypted customer code with IV: {iv}")
            return encrypted_text, iv

        except Exception as e:
            logger.error(f"An exception occurred while encrypting customer code: {e}", exc_info=True)
            raise Exception("Failed to encrypt customer code")