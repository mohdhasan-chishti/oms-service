"""
Wallet payment service for handling wallet-based payments.
"""

import logging
from typing import Dict, Any
from decimal import Decimal

from app.services.payment_service import PaymentService
from app.core.constants import PaymentStatus

# Integrations
from app.integrations.wallet_service import WalletService

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("wallet_payment_service")

class WalletPaymentService:
    """Service for handling wallet payments"""
    
    async def process_wallet_payment(self, customer_id: str, order_id: int, amount: Decimal, payment_id: str, description: str = None, related_id: str = None) -> Dict[str, Any]:
        """
        Process a wallet payment by debiting the wallet and creating payment record.
        
        Args:
            customer_id: Customer ID
            order_id: Order ID
            amount: Payment amount
            description: Payment description
            related_id: Optional related ID for wallet transaction (auto-generated if not provided)
            
        Returns:
            Dict with payment processing result
        """
        try:
            # Use provided related_id or generate one
            if not related_id:
                related_id = f"oms_{payment_id}_{order_id}"
            
            # Add wallet entry (debit)
            debit_result = await WalletService().add_wallet_entry(
                customer_id=customer_id,
                amount=amount,
                order_id=str(order_id),
                payment_id=payment_id,
                entry_type="debit",
                reference_type="order_payment",
                description=description or f"Payment for order {order_id}",
                related_id=related_id
            )

            if not debit_result.success:
                logger.warning(f"wallet_debit_failed | order_id={order_id} customer_id={customer_id} payment_id={payment_id} message={debit_result.message}")

                if "already been used" in debit_result.message:
                    logger.info(f"wallet_already_processed | order_id={order_id} customer_id={customer_id} payment_id={payment_id}")
                    return {
                        "success": True,
                        "message": "Wallet payment already processed",
                        "payment_id": payment_id,
                        "transaction_id": debit_result.data.get("transaction_id") if debit_result.data else None,
                        "status": "completed"
                    }

                # On any failure (e.g., insufficient balance, wrong OTP), mark payment as FAILED
                payment_service = PaymentService()
                await payment_service.update_payment_status(
                    payment_id=payment_id,
                    new_status=PaymentStatus.FAILED
                )

                return {
                    "success": False,
                    "message": debit_result.message,
                    "payment_id": payment_id,
                    "transaction_id": None,
                    "status": "failed"
                }

            # Success path: use the correct key exposed by WalletService().add_wallet_entry
            transaction_id = debit_result.data.get("transaction_id", None)

            # Update payment status to completed
            payment_service = PaymentService()
            update_result = await payment_service.update_payment_status(
                payment_id=payment_id,
                new_status=PaymentStatus.COMPLETED
            )

            if not update_result.get("success", False):
                logger.error(f"Failed to update payment status for {payment_id}: {update_result.get('message')}")
                
            logger.info(f"Wallet payment processed successfully: {payment_id}")

            return {
                "success": True,
                "message": "Wallet payment processed successfully",
                "payment_id": payment_id,
                "transaction_id": transaction_id,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Error processing wallet payment: {e}")
            # Best-effort mark as FAILED on unexpected errors
            try:
                payment_service = PaymentService()
                await payment_service.update_payment_status(payment_id=payment_id, new_status=PaymentStatus.FAILED)
            except Exception:
                logger.error(f"Failed to update payment status for {payment_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Wallet payment error: {str(e)}",
                "payment_id": payment_id,
                "transaction_id": None,
                "status": "failed"
            }

    async def confirm_wallet_payment(self, payment_id: str, order_id: int) -> Dict[str, Any]:
        """
        Confirm a wallet payment by confirming the wallet transaction.
        
        Args:
            payment_id: Payment ID (wallet_<transaction_id>)
            
        Returns:
            Dict with confirmation result
        """
        try:
            # Update payment status to completed
            payment_service = PaymentService()
            update_result = await payment_service.update_payment_status(
                payment_id=payment_id,
                new_status=PaymentStatus.COMPLETED
            )

            if not update_result.get("success", False):
                logger.error(f"Failed to update payment status for {payment_id}: {update_result.get("message", "")}")
                # Note: Wallet transaction is already confirmed, so we log but don't fail
            
            logger.info(f"Wallet payment confirmed successfully: {payment_id}")
            
            return {
                "success": True,
                "message": "Wallet payment confirmed successfully",
                "payment_id": payment_id,
                "transaction_id": None,
                "status": "confirmed"
            }
            
        except Exception as e:
            logger.error(f"Error confirming wallet payment: {e}")
            return {
                "success": False,
                "message": f"Wallet confirmation error: {str(e)}"
            }
    
    async def cancel_wallet_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Cancel a wallet payment by cancelling the wallet transaction.
        
        Args:
            payment_id: Payment ID (wallet_<transaction_id>)
            
        Returns:
            Dict with cancellation result
        """
        try:
            # Extract transaction ID from payment ID
            if not payment_id.startswith("wallet_"):
                logger.warning(f"wallet_cancel_invalid_payment_id | payment_id={payment_id}")
                return {
                    "success": False,
                    "message": "Invalid wallet payment ID format"
                }
            
            transaction_id = payment_id.replace("wallet_", "")
            
            # Cancel transaction with wallet service
            cancel_result = await WalletService().cancel_transaction(transaction_id)
            
            if not cancel_result.success:
                return {
                    "success": False,
                    "message": cancel_result.message
                }
            
            # Update payment status to failed
            payment_service = PaymentService()
            update_result = await payment_service.update_payment_status(
                payment_id=payment_id,
                new_status=PaymentStatus.FAILED
            )

            if not update_result.get("success", False):
                logger.error(f"Failed to update payment status for {payment_id}: {update_result.get("success", False)}")

            logger.info(f"Wallet payment cancelled successfully: {payment_id}")

            return {
                "success": True,
                "message": "Wallet payment cancelled successfully",
                "payment_id": payment_id,
                "transaction_id": transaction_id,
                "status": "cancelled"
            }
            
        except Exception as e:
            logger.error(f"Error cancelling wallet payment: {e}")
            return {
                "success": False,
                "message": f"Wallet cancellation error: {str(e)}"
            }



