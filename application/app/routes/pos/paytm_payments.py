"""
Paytm payment endpoints for POS system.

This module handles Paytm EDC payment initiation, status checking, and confirmation.
Uses polling mechanism (no webhooks) to check payment status.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from decimal import Decimal

from app.integrations.paytm_service import PaytmService
from app.integrations.potions_service import PotionsService
from app.services.payment_service import PaymentService
from app.services.payments.payment_processor import OrderPaymentProcessor
from app.services.order_service import OrderService
from app.core.constants import PaymentStatus, OrderStatus
from app.repository.payments import PaymentRepository
from app.dto.paytm_payments import (
    PaytmPaymentInitiateRequest,
    PaytmPaymentStatusRequest,
    PaytmPaymentConfirmRequest
)

from app.logging.utils import get_app_logger
logger = get_app_logger('pos.paytm_payments')

paytm_router = APIRouter(tags=["pos-paytm"])


@paytm_router.post("/paytm/initiate_payment")
async def initiate_paytm_payment(request_data: PaytmPaymentInitiateRequest):
    """
    Initiate Paytm POS payment.
    System automatically calculates unpaid amount for paytm_pos payments.

    Request:
    - order_id: Order ID (displayed on terminal)
    - terminal_id: EDC terminal ID (required)

    Response:
    - txn_id: Transaction ID for status polling
    - status: INITIATED
    - result_code: Paytm result code
    """
    try:
        logger.info(f"paytm_payment_initiate | order_id={request_data.order_id} calculating unpaid amount")
        repo = PaymentRepository()

        # Get order info (total amount)
        order_info = repo.get_order_info_by_order_id(request_data.order_id)
        if not order_info:
            raise HTTPException(status_code=404, detail="Order not found")

        total_amount = order_info.get("total_amount") or 0
        if total_amount is None:
            raise HTTPException(status_code=400, detail="Order total not available")

        # Get unpaid amount for paytm_pos payment mode
        payments = repo.get_payments_for_order(request_data.order_id)
        paytm_pos_payment = None
        for payment in payments or []:
            if payment.get("payment_mode") == "paytm_pos":
                paytm_pos_payment = payment
                break

        # Calculate unpaid amount for paytm_pos
        if not paytm_pos_payment:
            # No paytm_pos payment record found - cannot initiate payment
            raise HTTPException(status_code=400, detail="Order does not have paytm_pos payment mode configured")

        payment_amount = Decimal(str(paytm_pos_payment.get("payment_amount") or 0))
        if paytm_pos_payment.get("payment_status") == PaymentStatus.COMPLETED:
            amount = Decimal(0)
        else:
            amount = payment_amount

        if amount <= 0:
            raise HTTPException(status_code=400, detail="No unpaid amount pending for paytm_pos payment")

        # Check if there's an existing txn_id and verify its status with Paytm server
        existing_txn_id = paytm_pos_payment.get("payment_order_id")

        if existing_txn_id:
            stored_terminal_id = paytm_pos_payment.get("terminal_id")
            status_terminal_id = stored_terminal_id or request_data.terminal_id
            paytm_service = PaytmService(terminal_id=status_terminal_id)
            status_result = await paytm_service.check_payment_status(txn_id=existing_txn_id,order_id=request_data.order_id,terminal_id=status_terminal_id)

            paytm_status = status_result.get("status")
            logger.info(f"paytm_existing_txn_status | order_id={request_data.order_id} txn_id={existing_txn_id} status={paytm_status}")

            # If transaction is successful on Paytm, return existing txn_id
            if paytm_status in ["SUCCESS", "COMPLETED"]:
                logger.info(f"paytm_payment_already_successful | order_id={request_data.order_id} txn_id={existing_txn_id}")
                return {
                    "success": True,
                    "message": "Payment already completed",
                    "data": {
                        "txn_id": existing_txn_id,
                        "status": paytm_status,
                        "already_completed": True
                    }
                }

            # If PENDING, block reinitiate
            if paytm_status == "PENDING":
                logger.info(f"paytm_payment_pending | order_id={request_data.order_id} txn_id={existing_txn_id}")
                raise HTTPException(status_code=400, detail="Payment is already in progress. Please wait or check status.")

            # For FAILED or other status, allow reinitiate
            logger.info(f"paytm_generate_new_txn | order_id={request_data.order_id} previous_txn_id={existing_txn_id} previous_status={paytm_status}")
        
        # Initiate new payment
        logger.info(f"paytm_payment_initiate | order_id={request_data.order_id} calculated_amount={amount} terminal_id={request_data.terminal_id}")
        paytm_service = PaytmService(terminal_id=request_data.terminal_id)
        result = await paytm_service.initiate_payment(
            order_id=request_data.order_id,
            amount=amount,
            terminal_id=request_data.terminal_id
        )

        if not result.get("success"):
            logger.error(f"paytm_payment_failed | order_id={request_data.order_id} error={result.get('error')}")
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to initiate payment"))

        # Update payment record with new terminal_id and txn_id (payment_order_id)
        new_txn_id = result.get('txn_id')
        payment_internal_id = paytm_pos_payment.get("id")

        if payment_internal_id and new_txn_id:
            try:
                repo.update_paytm_payment_details(payment_internal_id=payment_internal_id, terminal_id=request_data.terminal_id, payment_order_id=new_txn_id)
            except Exception as e:
                logger.error(f"paytm_payment_record_update_failed | payment_id={payment_internal_id} error={e}", exc_info=True)

        logger.info(f"paytm_payment_initiated | order_id={request_data.order_id} txn_id={result.get('txn_id')}")
        return {
            "success": True,
            "message": "Payment initiated on terminal",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"paytm_payment_error | order_id={request_data.order_id} error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@paytm_router.post("/paytm/payment_status")
async def check_paytm_payment_status(request_data: PaytmPaymentStatusRequest):
    """
    Check payment status from Paytm.

    This endpoint is called by POS to poll payment status while customer
    completes payment on EDC machine.
    """
    try:
        logger.info(f"paytm_status_check_request | txn_id={request_data.txn_id} order_id={request_data.order_id}")
        paytm_service = PaytmService(terminal_id=request_data.terminal_id)
        result = await paytm_service.check_payment_status(
            txn_id=request_data.txn_id,
            order_id=request_data.order_id,
            terminal_id=request_data.terminal_id
        )

        if not result.get("success"):
            logger.warning(f"paytm_status_check_failed | txn_id={request_data.txn_id} error={result.get('message')}")
            return {
                "success": False,
                "message": result.get("message", "Failed to check payment status"),
                "data": result
            }

        status = result.get("status", "PENDING")
        logger.info(f"paytm_status_checked | txn_id={request_data.txn_id} status={status}")

        return {
            "success": True,
            "message": "Payment status retrieved successfully",
            "data": result
        }

    except Exception as e:
        logger.error(f"paytm_status_check_error | txn_id={request_data.txn_id} error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check payment status: {str(e)}")


@paytm_router.post("/paytm/confirm_payment")
async def confirm_paytm_payment(request_data: PaytmPaymentConfirmRequest, background_tasks: BackgroundTasks):
    """
    Confirm Paytm payment and update payment status in database.

    This endpoint:
    1. Verifies payment status with Paytm
    2. Updates payment record in database
    3. Triggers order completion if all payments are successful
    """
    try:
        logger.info(f"paytm_payment_confirm_request | txn_id={request_data.txn_id} order_id={request_data.order_id}")
        paytm_service = PaytmService(terminal_id=request_data.terminal_id)
        status_result = await paytm_service.check_payment_status(
            txn_id=request_data.txn_id,
            order_id=request_data.order_id,
            terminal_id=request_data.terminal_id
        )

        if not status_result.get("success"):
            logger.error(f"paytm_payment_confirm_status_check_failed | txn_id={request_data.txn_id}")
            raise HTTPException(status_code=400, detail=status_result.get("message", "Failed to verify payment status with Paytm"))

        paytm_status = status_result.get("status", "PENDING")
        if paytm_status == "SUCCESS":
            payment_status = PaymentStatus.COMPLETED
        elif paytm_status in ("FAILURE", "FAIL"):
            payment_status = PaymentStatus.FAILED
        else:
            payment_status = PaymentStatus.PENDING

        # Return 400 if payment failed
        if payment_status == PaymentStatus.FAILED:
            logger.warning(f"paytm_payment_failed | txn_id={request_data.txn_id} paytm_status={paytm_status} message={status_result.get('message')}")
            raise HTTPException(status_code=400, detail=f"Payment failed: {status_result.get('message', 'Unknown error')}")

        # Validate order_id and payment_id exist in a single query
        payment_repo = PaymentRepository()
        payment_record = payment_repo.get_payment_by_id_and_order(
            payment_id=request_data.payment_id,
            order_id=request_data.order_id
        )

        if not payment_record:
            logger.error(f"paytm_payment_validation_failed | payment_id={request_data.payment_id} order_id={request_data.order_id} reason=payment_or_order_not_found")
            raise HTTPException(status_code=400, detail=f"Payment ID {request_data.payment_id} does not exist for Order ID {request_data.order_id}")

        # Check if payment is already confirmed to prevent reprocessing
        current_payment_status = payment_record.get("payment_status")
        if current_payment_status == PaymentStatus.COMPLETED:
            logger.warning(f"paytm_payment_already_confirmed | payment_id={request_data.payment_id} order_id={request_data.order_id} current_status={current_payment_status}")
            raise HTTPException(status_code=400, detail=f"Payment ID {request_data.payment_id} is already confirmed. Cannot reprocess.")

        payment_service = PaymentService()
        update_result = await payment_service.update_payment_status(
            payment_id=request_data.payment_id,
            new_status=payment_status
        )

        if not update_result.get("success"):
            logger.error(f"paytm_payment_status_update_failed | payment_id={request_data.payment_id}")
            raise HTTPException(status_code=500, detail="Failed to update payment status")

        logger.info(f"paytm_payment_confirmed | txn_id={request_data.txn_id} payment_id={request_data.payment_id} status={payment_status}")
        # Orchestrate WMS flow when payment is successful
        if payment_status == PaymentStatus.COMPLETED:
            payment_repo = PaymentRepository()
            order = payment_repo.get_order_info_by_order_id(request_data.order_id)
            payment_records = payment_repo.get_payments_for_order(request_data.order_id)

            if order and payment_records and order.get('status') in [0, 10]:  # DRAFT=0, OPEN=10
                facility_name = order.get('facility_name')

                # Process all payments through the payment processor
                payment_processor = OrderPaymentProcessor()
                payments_status, sync_order = await payment_processor.process_paytm_pos_included_order_payment(
                    request_data.order_id, payment_records, request_data.txn_id, payment_status
                )

                order_service = OrderService()
                if payments_status:
                    order_result = await order_service.update_order_status(request_data.order_id, OrderStatus.OPEN)
                    logger.info(f"order_status_update_post_payment | order_id={request_data.order_id} status={int(OrderStatus.OPEN)}, result={order_result}")

                    if sync_order:
                        potions_service = PotionsService()
                        background_tasks.add_task(potions_service.sync_order_by_id, facility_name, request_data.order_id, order_service)
                        logger.info(f"paytm_payment_confirm: WMS sync queued | order_id={request_data.order_id}")
                else:
                    logger.error(f"paytm_payment_confirm: Payment processing failed | order_id={request_data.order_id}")
            else:
                logger.info(f"paytm_payment_confirm: Order processing already in progress | order_id={request_data.order_id} order_exists={order is not None} status={order.get('status') if order else 'unknown'}")

        return {
            "success": True,
            "message": "Payment confirmed successfully",
            "data": {
                "payment_id": request_data.payment_id,
                "txn_id": request_data.txn_id,
                "order_id": request_data.order_id,
                "payment_status": PaymentStatus.get_description(payment_status),
                "paytm_status": paytm_status,
                "bank_txn_id": status_result.get("bank_txn_id"),
                "payment_mode": status_result.get("payment_mode")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"paytm_payment_confirm_error | txn_id={request_data.txn_id} error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to confirm payment: {str(e)}")
