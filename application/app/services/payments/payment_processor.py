
# Services
from app.services.wallet_payment_service import WalletPaymentService
from app.services.payment_service import PaymentService

# Repository
from app.repository.payments import PaymentRepository

# Constants
from app.core.constants import PaymentStatus

import json

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("order_payment_processor")

class OrderPaymentProcessor:
    def __init__(self):
        pass
    
    async def process_order_payment(self, order_id: str, payment_records = [], customer_id: str = None):

        # Single Payment Mode
        # if its wallet only call wallet and debut the amount 
        # if its only cash/online then make the status as completed

        ## Combinations Payment Mode
        # its wallet + cash/online debit the amount from wallet and make the status as completed

        # Skip order sync for online payment gateways (Razorpay, Cashfree)
        sync_order = False
        payment_modes = []
        for payment_record in payment_records:
            mode = payment_record.get("payment_mode", "").lower()
            payment_modes.append(mode)
        
        # Skip sync for online payment gateways as they handle their own webhooks
        if any(mode in ["razorpay", "cashfree", "paytm_pos"] for mode in payment_modes):
            logger.info(f"Skipping sync for online payment gateway: {payment_modes}")
            return True, sync_order

        # sort the payment records based on the payment mode # to be checked

        try:
            description = "Payment for order " + order_id
            for payment_record in payment_records:
                if payment_record.get("payment_mode", "").lower() == "wallet":
                    wallet_payment_service = WalletPaymentService()
                    payment_id = payment_record.get("payment_id")
                    amount = payment_record.get("amount")
                    wallet_result = await wallet_payment_service.process_wallet_payment(customer_id=customer_id,
                        order_id=order_id,
                        amount=amount,
                        payment_id=payment_id, 
                        description=description
                    )
                    logger.info(f"Wallet payment processed successfully: {payment_id}")
                    if not wallet_result.get("success", False):
                        logger.error(f"Wallet payment failed: {json.dumps(wallet_result)}")
                        return False, sync_order

                elif payment_record.get("payment_mode", "").lower() in {"cash", "online"}:
                    payment_id = payment_record.get("payment_id")
                    payment_service = PaymentService()
                    cash_result = await payment_service.update_payment_status(
                        payment_id=payment_id,
                        new_status=PaymentStatus.COMPLETED
                    )
                    logger.info(f"Cash-like payment processed successfully: {payment_id}")
                    if not cash_result.get("success", False):
                        logger.error(f"Cash-like payment failed: {json.dumps(cash_result)}")
                        return False, sync_order

            sync_order = True
            return True, sync_order

        except Exception as e:
            logger.error(f"Error processing order payment: {str(e)}")
            return False, sync_order

    async def process_razorpay_included_order_payment(self, order_id: str, payment_records = [], razorpay_payment_id: str = None, razorpay_status: int = None):

        # if the payment mode is razorpay then update the payment status as completed
        # if the payment mode is razorpay and cash/online then update the payment status as completed
        # if the payment mode is razorpay and wallet debit the amount from wallet and make the status as completed
        # Three Combinations
        # 1. razorpay + cash/online + wallet - debit the amount from wallet and make the status as completed

        sync_order = False
        # sort the payment records based on the payment mode # to be checked

        try:
            description = "Payment for order " + order_id
            
            # Sort payments: gateway (razorpay/cashfree) (0), wallet (1), cash/online (2)
            payment_records = sorted(payment_records, key=lambda p: (0 if p.get('payment_mode', '').lower() in ['razorpay', 'cashfree'] else (1 if p.get('payment_mode', '').lower() == 'wallet' else 2)))

            for payment_record in payment_records:
                if payment_record.get("payment_mode", "").lower() == "wallet":
                    wallet_payment_service = WalletPaymentService()
                    payment_id = payment_record.get("payment_id")
                    amount = float(payment_record.get("payment_amount"))
                    customer_id = payment_record.get("customer_id")
                    wallet_result = await wallet_payment_service.process_wallet_payment(customer_id=customer_id,
                        order_id=order_id,
                        amount=amount,
                        payment_id=payment_id,
                        description=description,
                        related_id=f"oms_{payment_id}_{order_id}"
                    )
                    logger.info(f"Wallet payment processed successfully: {payment_id}")
                    if not wallet_result.get("success", False):
                        logger.error(f"Wallet payment failed: {json.dumps(wallet_result)}")
                        return False, sync_order

                elif payment_record.get("payment_mode", "").lower() in {"cash", "online"}:
                    payment_id = payment_record.get("payment_id")
                    payment_service = PaymentService()
                    cash_result = await payment_service.update_payment_status(
                        payment_id=payment_id,
                        new_status=PaymentStatus.COMPLETED
                    )
                    logger.info(f"Cash-like payment processed successfully: {payment_id}")
                    if not cash_result.get("success", False):
                        logger.error(f"Cash-like payment failed: {json.dumps(cash_result)}")
                        return False, sync_order

                elif payment_record.get("payment_mode", "").lower() == "razorpay":
                    payment_id = razorpay_payment_id
                    payment_internal_id = payment_record.get("id")
                    # update the payment_id in the payment_details table
                    payment_repo = PaymentRepository()
                    payment_repo.upadate_the_razorpay_payment_id(payment_internal_id, payment_id)
                    payment_service = PaymentService()
                    razorpay_result = await payment_service.update_payment_status(
                        payment_id=payment_id,
                        new_status=razorpay_status
                    )
                    logger.info(f"Razorpay payment processed successfully: {payment_id}")
                    if not razorpay_result.get("success", False):
                        logger.error(f"Razorpay payment status update failed: {json.dumps(razorpay_result)}")
                        sync_order = False
                        break
                    elif razorpay_status == 52:
                        logger.warning(f"Razorpay payment failed: {json.dumps(razorpay_result)}")
                        sync_order = False
                        break

                elif payment_record.get("payment_mode", "").lower() == "cashfree":
                    payment_id = str(razorpay_payment_id)  # Use same payment_id parameter for Cashfree
                    payment_internal_id = payment_record.get("id")
                    payment_mode_name = payment_record.get("payment_mode", "").lower()
                    # update the payment_id in the payment_details table
                    payment_repo = PaymentRepository()
                    payment_repo.upadate_the_razorpay_payment_id(payment_internal_id, payment_id)
                    payment_service = PaymentService()
                    cashfree_result = await payment_service.update_payment_status(
                        payment_id=payment_id,
                        new_status=razorpay_status
                    )
                    logger.info(f"{payment_mode_name.capitalize()} payment processed successfully: {payment_id}")
                    if not cashfree_result.get("success", False):
                        logger.error(f"{payment_mode_name.capitalize()} payment status update failed: {json.dumps(cashfree_result)}")
                        sync_order = False
                        break
                    elif razorpay_status == 52:
                        logger.warning(f"{payment_mode_name.capitalize()} payment failed: {json.dumps(cashfree_result)}")
                        sync_order = False
                        break

            else:
                # loop didnt break, so all payments processed successfully
                sync_order = True
                return True, sync_order

            # If we broke out of the loop due to a failure, return failure and don't sync
            return False, sync_order

        except Exception as e:
            logger.error(f"Error processing order payment: {str(e)}")
            return False, sync_order

    async def process_paytm_pos_included_order_payment(self, order_id: str, payment_records = [], paytm_txn_id: str = None, paytm_status: int = None):
        """
        Process Paytm POS payment along with other payment modes (wallet, cash/online).
        
        Similar to Razorpay, handles combinations:
        1. paytm_pos only
        2. paytm_pos + cash/online
        3. paytm_pos + wallet
        4. paytm_pos + cash/online + wallet
        """
        sync_order = False

        try:
            description = "Payment for order " + order_id
            
            # Sort payments: paytm_pos (0), wallet (1), cash/online (2)
            payment_records = sorted(payment_records, key=lambda p: (0 if p.get('payment_mode', '').lower() == 'paytm_pos' else (1 if p.get('payment_mode', '').lower() == 'wallet' else 2)))

            for payment_record in payment_records:
                if payment_record.get("payment_mode", "").lower() == "wallet":
                    wallet_payment_service = WalletPaymentService()
                    payment_id = payment_record.get("payment_id")
                    amount = float(payment_record.get("payment_amount"))
                    customer_id = payment_record.get("customer_id")
                    wallet_result = await wallet_payment_service.process_wallet_payment(
                        customer_id=customer_id,
                        order_id=order_id,
                        amount=amount,
                        payment_id=payment_id,
                        description=description,
                        related_id=f"oms_{payment_id}_{order_id}"
                    )
                    logger.info(f"Wallet payment processed successfully: {payment_id}")
                    if not wallet_result.get("success", False):
                        logger.error(f"Wallet payment failed: {json.dumps(wallet_result)}")
                        return False, sync_order

                elif payment_record.get("payment_mode", "").lower() in {"cash", "online"}:
                    payment_id = payment_record.get("payment_id")
                    payment_service = PaymentService()
                    cash_result = await payment_service.update_payment_status(
                        payment_id=payment_id,
                        new_status=PaymentStatus.COMPLETED
                    )
                    logger.info(f"Cash-like payment processed successfully: {payment_id}")
                    if not cash_result.get("success", False):
                        logger.error(f"Cash-like payment failed: {json.dumps(cash_result)}")
                        return False, sync_order

                elif payment_record.get("payment_mode", "").lower() == "paytm_pos":
                    payment_id = paytm_txn_id
                    payment_internal_id = payment_record.get("id")
                    # Update the paytm transaction ID in the payment_details table
                    payment_repo = PaymentRepository()
                    payment_repo.update_paytm_txn_id(payment_internal_id, payment_id)
                    payment_service = PaymentService()
                    paytm_result = await payment_service.update_payment_status(
                        payment_id=payment_id,
                        new_status=paytm_status
                    )
                    logger.info(f"Paytm POS payment processed successfully: {payment_id}")
                    if not paytm_result.get("success", False) or paytm_status == PaymentStatus.FAILED:
                        logger.error(f"Paytm POS payment failed: {json.dumps(paytm_result)}")
                        sync_order = False
                        break

            else:
                # loop didn't break, so all payments processed successfully
                sync_order = True
                return True, sync_order

            # If we broke out of the loop due to a failure, return failure and don't sync
            return False, sync_order

        except Exception as e:
            logger.error(f"Error processing paytm_pos order payment: {str(e)}")
            return False, sync_order

        