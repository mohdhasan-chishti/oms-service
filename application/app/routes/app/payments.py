"""
Payment routes for Razorpay integration in the OMS system.

This module handles payment-related API endpoints including order creation,
payment verification, and webhook handling.
"""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.integrations.potions_service import PotionsService

# Payment repository
from app.repository.payments import PaymentRepository
from app.services.payments.payment_processor import OrderPaymentProcessor

from app.dto.payments import (
    PaymentOrderCreate,
    PaymentOrderResponse,
    PaymentVerification,
    PaymentVerificationResponse,
)
from app.integrations.razorpay_service import razorpay_service
from app.core.order_functions import get_order_by_id, get_payment_status_for_order, update_existing_payment
from app.core.constants import PaymentStatus, OrderStatus

from app.services.order_service import OrderService

# Request context
from app.middlewares.request_context import request_context

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

payment_router = APIRouter(tags=["payments"])


@payment_router.post("/create_payment_order", response_model=PaymentOrderResponse)
async def create_payment_order(payment_order: PaymentOrderCreate, request: Request):
    """
    Create a Razorpay order for payment processing.
    This endpoint creates a corresponding Razorpay order for an existing OMS order,
    enabling the Flutter app to initiate payment.
    """
    try:
        request_context.module_name = 'route_payments'
        # Verify that the OMS order exists
        order = await get_order_by_id(payment_order.order_id)
        if not order:
            logger.warning(f"payment_order_create_not_found | order_id={payment_order.order_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Order {payment_order.order_id} not found"
            )

        # Prepare customer details
        customer_details = {
            "customer_id": payment_order.customer_id,
            "customer_name": payment_order.customer_name,
            "customer_email": payment_order.customer_email,
            "customer_phone": payment_order.customer_phone
        }

        # Create Razorpay order
        result = await razorpay_service.create_razorpay_order(
            order_id=payment_order.order_id,
            amount=payment_order.amount,
            customer_details=customer_details,
            notes=payment_order.notes
        )

        if result["success"]:
            return PaymentOrderResponse(
                success=True,
                message="Payment order created successfully",
                razorpay_order_id=result["razorpay_order_id"],
                amount=result["amount"],
                amount_paise=result["amount_paise"],
                currency=result["currency"],
                key_id=result["key_id"],
                order_id=payment_order.order_id,
                created_at=result["created_at"]
            )
        else:
            if result.get("skipped"):
                return PaymentOrderResponse(
                    success=False,
                    message="Razorpay integration is disabled"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result.get("message", "Failed to create payment order")
                )
    
    except HTTPException:
        logger.warning(f"payment_order_create_http_exception | order_id={payment_order.order_id} customer_id={payment_order.customer_id}")
        raise
    except Exception as e:
        logger.error(f"payment_order_create_error | order_id={payment_order.order_id} customer_id={payment_order.customer_id} error={e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating payment order"
        )


@payment_router.post("/verify_payment", response_model=PaymentVerificationResponse)
async def verify_payment(verification: PaymentVerification, background_tasks: BackgroundTasks):
    """
    Verify payment signature and update order status.

    This endpoint is called by the Flutter app after successful payment
    to verify the payment and update the order status.
    """
    try:
        request_context.module_name = 'route_payments'
        # Verify payment signature
        is_verified = await razorpay_service.verify_payment_signature(
            verification.razorpay_order_id,
            verification.razorpay_payment_id,
            verification.razorpay_signature
        )

        if not is_verified:
            logger.warning(f"payment_verification_failed | order_id={verification.oms_order_id} payment_id={verification.razorpay_payment_id}")
            return PaymentVerificationResponse(
                success=False,
                message="Payment signature verification failed",
                verified=False
            )

        # Get payment details from Razorpay
        payment_result = await razorpay_service.get_payment_details(
            verification.razorpay_payment_id
        )

        if not payment_result["success"]:
            logger.warning(f"payment_details_fetch_failed | payment_id={verification.razorpay_payment_id}")
            return PaymentVerificationResponse(
                success=False,
                message="Failed to fetch payment details",
                verified=True
            )

        payment = payment_result["payment"]
        razorpay_status = payment["status"]
        logger.info(f"payment_details_fetch_success | payment_id={verification.razorpay_payment_id} status={razorpay_status} payment={payment}")

        # Map Razorpay status to our payment status
        payment_status = PaymentStatus.COMPLETED if razorpay_status == "captured" else PaymentStatus.FAILED

        order_id = verification.oms_order_id

        if payment_status == PaymentStatus.COMPLETED:
            success_flag = True
            message = "Payment verified successfully"
        else:
            success_flag = False
            message = "Payment verification failed"

        return PaymentVerificationResponse(
            success=success_flag,
            message=message,
            verified=True,
            order_id=order_id,
            payment_status=str(payment_status)  # Convert integer to string
        )

    except Exception as e:
        logger.error(f"payment_verification_error | order_id={order_id} payment_id={verification.razorpay_payment_id} error={e}", exc_info=True)
        return PaymentVerificationResponse(
            success=False,
            message="Internal server error during payment verification",
            error=str(e)
        )


@payment_router.get("/payment_status/{order_id}")
async def get_payment_status(order_id: str):
    """
    Get payment status for an order (from payments table only).
    
    This endpoint returns payment information from the payments table,
    completely separate from order status.
    """
    try:
        request_context.module_name = 'route_payments'
        # Verify order exists
        order = await get_order_by_id(order_id)
        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"Order {order_id} not found"
            )

        # Get payment status from payments table only
        payment_summary = await get_payment_status_for_order(order_id)

        return {
            "success": True,
            "order_id": order_id,
            "order_status": OrderStatus.get_customer_status_name(order.get("status")),  # Order status (separate from payment)
            "payment_summary": payment_summary  # Payment status (from payments table)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"payment_status_error | order_id={order_id} error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get payment status")

