from app.services.boto3_service import Boto3Service
from app.validations.orders import OrderInvoiceValidator, OrderUserValidator
from fastapi import HTTPException

from app.logging.utils import get_app_logger
logger = get_app_logger('invoice_core')
from app.config.settings import OMSConfigs
configs = OMSConfigs()
boto3_service = Boto3Service()


async def get_invoice_url_core(user_id: str, invoice_s3_url: str, order_id: str):
    try:
        invoice_validator = OrderInvoiceValidator()
        validator = OrderUserValidator(order_id=order_id, user_id=user_id)
        validator.validate_order_with_user()
        valid = invoice_validator.validate_invoice_s3_url_with_order_id(invoice_s3_url, order_id)
        if not valid:
            raise HTTPException(status_code=404, detail="Invoice not found for the specified order or invalid invoice URL")
        # Generate presigned URL
        if configs.AWS_INTEGRATION_ENABLED:
            presigned_url = boto3_service.get_presigned_url(invoice_s3_url)
        else:
            logger.warning(f"AWS integration is not enabled. Cannot generate invoice URL for order: {order_id}")
            raise HTTPException(status_code=500, detail="AWS integration is not enabled. Cannot generate invoice URL")

        logger.info(f"Successfully generated invoice URL for order: {order_id}")
        
        return {
            "success": True,
            "presigned_url": presigned_url,
            "order_id": order_id,
            "expires_in": boto3_service.expiry_seconds,
            "message": "Invoice URL generated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating invoice URL for order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate invoice URL")
