
import os
from dotenv import load_dotenv
load_dotenv()

class OMSConfigs:
    def __init__(self):

        # Database settings
        self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rozana_oms")
        self.DATABASE_READ_URL = os.getenv("DATABASE_READ_URL", self.DATABASE_URL)

        # Redis settings
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.REDIS_CACHE_DB = int(os.getenv("REDIS_CACHE_DB", "3"))
        self.FIREBASE_AUTH_CACHE_ENABLED = os.getenv("FIREBASE_AUTH_CACHE_ENABLED", "true").lower() == "true"
        self.FIREBASE_AUTH_CACHE_TTL_SECONDS = int(os.getenv("FIREBASE_AUTH_CACHE_TTL_SECONDS", "300"))
        self.FIREBASE_AUTH_CACHE_PREFIX = os.getenv("FIREBASE_AUTH_CACHE_PREFIX", "firebase:id_token")

        # Environment settings
        self.APPLICATION_ENVIRONMENT = os.getenv("APPLICATION_ENVIRONMENT", "UAT")
        self.APP_NAME = os.getenv('APP_NAME', 'rozana-oms')
        self.APP_VERSION = os.getenv('APP_VERSION', '4.0.0')

        # Typesence settings
        self.TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "localhost")
        self.TYPESENSE_PORT = os.getenv("TYPESENSE_PORT", "8108")
        self.TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
        self.TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY", "")
        self.TYPESENSE_COLLECTION_NAME = os.getenv("TYPESENSE_COLLECTION_NAME", "facility_products")
        self.TYPESENSE_FREEBIES_COLLECTION_NAME = os.getenv("TYPESENSE_FREEBIES_COLLECTION_NAME", "freebies_products")
        self.TYPESENSE_INDEX_SIZE = int(os.getenv("TYPESENSE_INDEX_SIZE", "10"))

        # Razorpay settings
        self.RAZORPAY_INTEGRATION_ENABLED = os.getenv("RAZORPAY_INTEGRATION_ENABLED", "false").lower() == "true"
        self.RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
        self.RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
        self.RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        self.RAZORPAY_BASE_URL = os.getenv("RAZORPAY_BASE_URL", "https://api.razorpay.com/v1")
        self.RAZORPAY_CURRENCY = os.getenv("RAZORPAY_CURRENCY", "INR")
        self.RAZORPAY_TIMEOUT = int(os.getenv("RAZORPAY_TIMEOUT", "30"))
        
        # Cashfree settings
        self.CASHFREE_INTEGRATION_ENABLED = os.getenv("CASHFREE_INTEGRATION_ENABLED", "false").lower() == "true"
        self.CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID", "")
        self.CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "")
        self.CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET", "")
        self.CASHFREE_BASE_URL = os.getenv("CASHFREE_BASE_URL", "https://sandbox.cashfree.com/pg")
        self.CASHFREE_WEBHOOK_URL = os.getenv("CASHFREE_WEBHOOK_URL", "")
        self.CASHFREE_RETURN_URL = os.getenv("CASHFREE_RETURN_URL", "")
        self.CASHFREE_CURRENCY = os.getenv("CASHFREE_CURRENCY", "INR")
        self.CASHFREE_TIMEOUT = int(os.getenv("CASHFREE_TIMEOUT", "30"))

        self.PAYTM_INTEGRATION_ENABLED = os.getenv("PAYTM_INTEGRATION_ENABLED", "false").lower() == "true"
        self.PAYTM_MERCHANT_ID = os.getenv("PAYTM_MERCHANT_ID", "")
        self.PAYTM_MERCHANT_KEY = os.getenv("PAYTM_MERCHANT_KEY", "")
        self.PAYTM_BASE_URL = os.getenv("PAYTM_BASE_URL", "https://securegw-stage.paytm.in/ecr")
        self.PAYTM_TIMEOUT = int(os.getenv("PAYTM_TIMEOUT", "60"))
        self.PAYTM_CHANNEL_ID = os.getenv("PAYTM_CHANNEL_ID", "EDC")

        # Wallet settings
        self.WALLET_INTEGRATION_ENABLED = os.getenv("WALLET_INTEGRATION_ENABLED", "false").lower() == "true"
        self.WALLET_BASE_URL = os.getenv("WALLET_BASE_URL", "")
        self.WALLET_INTERNAL_API_KEY = os.getenv("WALLET_INTERNAL_API_KEY", "")

        # Sentry settings
        self.SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "false").lower() == "true"
        self.SENTRY_DSN = os.getenv("SENTRY_DSN", "")
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.SENTRY_RELEASE = os.getenv("SENTRY_RELEASE", "rozana-oms-service@1.0.0")
        self.SENTRY_TRACES_SAMPLE_RATE = os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")
        self.SENTRY_PROFILES_SAMPLE_RATE = os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")

        # Potions settings
        self.POTIONS_INTEGRATION_ENABLED = os.getenv("POTIONS_INTEGRATION_ENABLED", "true").lower() == "true"
        self.POTIONS_CLIENT_ID = os.getenv("POTIONS_CLIENT_ID", "")
        self.POTIONS_CLIENT_SECRET = os.getenv("POTIONS_CLIENT_SECRET", "")
        self.POTIONS_BASE_URL = os.getenv("POTIONS_BASE_URL", "")
        self.POTIONS_TIMEOUT = int(os.getenv("POTIONS_TIMEOUT", "60"))

        # Auth settings
        self.TOKEN_VALIDATION_URL = os.getenv("TOKEN_VALIDATION_URL", "")
        self.FIRESTORE_DATABASE=os.getenv("FIRESTORE_DATABASE", "")

        # Encryption settings
        self.ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "MOoRZhMT3c5yrE1A")

        # Product settings
        self.STOCK_CHECK_ENABLED = os.getenv("STOCK_CHECK_ENABLED", "false").lower() == "true"
        self.PRICE_CHECK_ENABLED = os.getenv("PRICE_CHECK_ENABLED", "true").lower() == "true"

        # Logging Core settings
        self.ASYNC_LOGGING = os.getenv("ASYNC_LOGGING", "false").lower() == "true"
        self.BATCH_PROCESSING = os.getenv("BATCH_PROCESSING", "false").lower() == "true"
        self.FIREHOSE_ENABLED = os.getenv("FIREHOSE_ENABLED", "false").lower() == "true"
        self.AUDIT_LOGGING_ENABLED = os.getenv("AUDIT_LOGGING_ENABLED", "false").lower() == "true"
        self.CAPTURE_RESPONSE_BODY = os.getenv("CAPTURE_RESPONSE_BODY", "false").lower() == "true"
        self.LOG_DEBUG_PRINTS = os.getenv("LOG_DEBUG_PRINTS", "false").lower() == "true"
        
        # Logging Stream Names
        self.APP_LOGS_STREAM_NAME = os.getenv("APP_LOGS_STREAM_NAME", "")
        self.AUDIT_LOGS_STREAM_NAME = os.getenv("AUDIT_LOGS_STREAM_NAME", "")
        self.AUDIT_LOGS_GET_STREAM_NAME = os.getenv("AUDIT_LOGS_GET_STREAM_NAME", "")
        self.LOG_BUFFER_TIMEOUT = int(os.getenv("LOG_BUFFER_TIMEOUT", "600"))

        # Logging Buffer Sizes
        self.APP_LOGS_CAPACITY = int(os.getenv("APP_LOGS_CAPACITY", "50"))
        self.AUDIT_LOGS_CAPACITY = int(os.getenv("AUDIT_LOGS_CAPACITY", "50"))
        self.AUDIT_LOGS_GET_CAPACITY = int(os.getenv("AUDIT_LOGS_GET_CAPACITY", "50"))
        self.LOG_PROCESSOR_POOL_SIZE = int(os.getenv("LOG_PROCESSOR_POOL_SIZE", "2"))
        self.MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "10"))

        # Firehose settings
        self.FIREHOSE_REGION_NAME = os.getenv("FIREHOSE_REGION_NAME", "ap-south-1")
        self.FIREHOSE_ACCESS_KEY_ID = os.getenv("FIREHOSE_ACCESS_KEY_ID", "")
        self.FIREHOSE_SECRET_ACCESS_KEY = os.getenv("FIREHOSE_SECRET_ACCESS_KEY", "")
        self.FIREHOSE_RETRY_COUNT = int(os.getenv("FIREHOSE_RETRY_COUNT", "3"))
        self.FIREHOSE_RETRY_DELAY = int(os.getenv("FIREHOSE_RETRY_DELAY", "1"))

        self.CAP_QUANTITY = int(os.getenv("CAP_QUANTITY", "20"))
        self.SAFETY_QUANTITY = int(os.getenv("SAFETY_QUANTITY", "10"))
        self.UPDATE_TYPESENSE_ENABLED = os.getenv("UPDATE_TYPESENSE_ENABLED", "false").lower() == "true"

        self.CURRENT_ORDER_LIMIT = int(os.getenv("CURRENT_ORDER_LIMIT", "10"))
        self.MARIADB_DATABASE_URL = os.getenv("MARIADB_DATABASE_URL", "")
        self.AWS_OLD_BASE_URL = os.getenv("AWS_OLD_BASE_URL", "https://djpw4cfh60y52.cloudfront.net/")

        self.AWS_INTEGRATION_ENABLED = os.getenv("AWS_INTEGRATION_ENABLED", "false").lower() == "true"
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "ap-south-1")
        self.AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
        self.S3_PRESIGNED_URL_EXPIRY_SECONDS = int(os.getenv("S3_PRESIGNED_URL_EXPIRY_SECONDS", "3600"))

        # MobileNXT OTP settings
        self.MOBILENXT_ACCESS_KEY = os.getenv("MOBILENXT_ACCESS_KEY", "")
        self.MOBILENXT_TID = os.getenv("MOBILENXT_TID", "")
        self.MOBILENXT_OTP_LENGTH = int(os.getenv("MOBILENXT_OTP_LENGTH", "6"))
        self.APP_SIGNATURE = os.getenv("APP_SIGNATURE", "")
        self.MOBILENXT_OTP_EXPIRY = int(os.getenv("MOBILENXT_OTP_EXPIRY", "300"))

        # Transaction Lock settings
        self.TRANSACTION_LOCK_TTL_SECONDS = int(os.getenv("TRANSACTION_LOCK_TTL_SECONDS", "10"))
        self.BILLER_CUSTOMER_LOCK_TTL_SECONDS = int(os.getenv("BILLER_CUSTOMER_LOCK_TTL_SECONDS", "10"))

        # Order ETA Timing settings
        self.STORE_OPEN_TIME = os.getenv("STORE_OPEN_TIME", "2:30")  # Format: HH:MM UTC
        self.STORE_CLOSE_TIME = os.getenv("STORE_CLOSE_TIME", "12:30")  # Format: HH:MM UTC
        self.ETA_DIFF_MINUTES = int(os.getenv("ETA_DIFF_MINUTES", "181"))
        self.ETA_ADJUST_MINUTES = int(os.getenv("ETA_ADJUST_MINUTES", "210"))

         # Skip stock check for marketplaces (comma-separated, e.g., "CAFE,ONDC")
        stock_skip_check_str = os.getenv("STOCK_SKIP_CHECK", "")
        # Filter out empty strings after splitting and convert to uppercase
        self.STOCK_SKIP_CHECK = [m.strip().lower() for m in stock_skip_check_str.split(",") if m.strip()]