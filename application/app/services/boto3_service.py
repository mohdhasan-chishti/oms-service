
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional
import os
from app.logging.utils import get_app_logger

logger = get_app_logger('boto3_service')

from app.config.settings import OMSConfigs
configs = OMSConfigs()

class Boto3Service:
    """
    Service class for handling AWS S3 operations, specifically for invoice file access.
    """
    
    def __init__(self):
        """
        Initialize S3 service with AWS credentials from environment variables.
        """

        self.aws_access_key_id = configs.AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = configs.AWS_SECRET_ACCESS_KEY
        self.aws_region = configs.AWS_S3_REGION_NAME
        self.bucket_name = configs.AWS_STORAGE_BUCKET_NAME
        self.expiry_seconds = configs.S3_PRESIGNED_URL_EXPIRY_SECONDS
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
        
        logger.info(f"Boto3Service initialized for bucket: {self.bucket_name}")
    
    def get_presigned_url(self, s3_key: str) -> str:
        """
        Generate a presigned URL for downloading a file from S3.
        """
        try:
            # First check if the object exists
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)

            # Generate presigned URL
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=self.expiry_seconds
            )

            logger.info(f"Generated presigned URL for key: {s3_key}")
            return presigned_url

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"S3 object not found: {s3_key}")
                raise Exception(f"Invoice file not found in S3: {s3_key}")
            else:
                logger.error(f"AWS S3 error: {str(e)}")
                raise Exception(f"Failed to generate presigned URL: {str(e)}")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise Exception("AWS credentials not configured properly")
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {str(e)}")
            raise Exception(f"Failed to generate presigned URL: {str(e)}")
