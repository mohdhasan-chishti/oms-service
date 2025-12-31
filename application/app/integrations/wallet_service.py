"""
External Wallet Service for handling wallet operations.

This service communicates with an external wallet API to handle
wallet balance checks, debit operations, and transaction confirmations.
"""

import httpx
from typing import Dict, Any, Optional
from decimal import Decimal
import uuid
from pydantic import BaseModel

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("wallet_service")

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

class WalletServiceReturnMessage(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    suppress_error_logs: Optional[bool] = None


class WalletService:
    """Service for communicating with external wallet API"""

    def __init__(self):
        self.wallet_enabled = configs.WALLET_INTEGRATION_ENABLED
        self.wallet_api_url = configs.WALLET_BASE_URL
        self.wallet_api_key = configs.WALLET_INTERNAL_API_KEY
        self.timeout = 30  # seconds

        if not self.wallet_enabled or not self.wallet_api_url or not self.wallet_api_key:
            logger.error("Wallet integration is disabled or not configured")
            raise ValueError("Wallet integration is disabled or not configured")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for wallet API requests"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "Rozana-OMS/1.0",
            "X-API-Key": self.wallet_api_key
        }

    def return_message(self, success: bool, message: str, data: Optional[Dict[str, Any]] = None, suppress_error_logs: Optional[bool] = None) -> WalletServiceReturnMessage:
        return WalletServiceReturnMessage(success=success, message=message, data=data, suppress_error_logs=suppress_error_logs)

    async def check_balance(self, customer_id: str) -> WalletServiceReturnMessage:
        """
        Check wallet balance for a customer.
        Args:
            customer_id: Customer ID
        Returns:
            Dict with balance information
        """
        self.url = f"{self.wallet_api_url}/balance/{customer_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url, headers=self._get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    return self.return_message(success=True,
                        message="Wallet balance checked successfully",
                        data={
                            "balance": float(data.get("balance", 0.0)),
                            "currency": data.get("currency", "INR"),
                            "is_active": data.get("is_active", True)
                        }
                    )
                elif response.status_code == 404:
                    logger.warning(f"Wallet not found during balance check | customer_id={customer_id}")
                    return self.return_message(success=False, message="Wallet not found", data={"balance": 0.0})
                else:
                    logger.error(f"Balance check failed: {response.status_code} - {response.text}")
                    return self.return_message(success=False, message=f"Balance check failed: {response.status_code}", data={"balance": 0.0})
        except httpx.TimeoutException:
            logger.error("Wallet service timeout during balance check")
            return self.return_message(success=False, message="Wallet service timeout", data={"balance": 0.0})
        except Exception as e:
            logger.error(f"Error checking wallet balance: {e}")
            return self.return_message(success=False, message=f"Balance check error: {str(e)}", data={"balance": 0.0})

    async def add_wallet_entry(self, customer_id: str, amount: Decimal, order_id: str, payment_id: str, entry_type: str = "debit", reference_type: str = "order_payment", description: str = None, related_id: str = None) -> WalletServiceReturnMessage:
        """
        Add wallet entry (debit/credit) using the actual wallet API format.
        Args:
            customer_id: Customer ID
            amount: Amount for the entry
            order_id: Order ID for reference
            payment_id: Payment ID for reference
            entry_type: "debit" or "credit"
            reference_type: Type of reference (e.g., "order_payment")
            description: Optional description
            related_id: Optional related ID (if not provided, one will be generated)
        Returns:
            Dict with wallet entry result
        """
        self.url = f"{self.wallet_api_url}/internal/wallet-entry/{customer_id}/add-entry"
        try:
            if not related_id:
                related_id = f"oms_{payment_id}_{uuid.uuid4().hex[:8]}"
            payload = {
                "related_id": related_id,
                "wallet_amt": float(amount),
                "entry_type": entry_type,
                "description": description or f"Payment for order {order_id}",
                "reference_type": reference_type
            }

            # Use the actual API endpoint format
            headers = self._get_headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    return self.return_message(success=True, message="Wallet entry added successfully",
                        data={
                            "transaction_id": related_id,
                            "amount": float(amount),
                            "balance_after": data.get("balance_after", 0.0),
                            "status": data.get("status", "completed")
                        }
                    )
                elif response.status_code == 400:
                    data = response.json()
                    logger.warning(f"Wallet entry rejected with 400 | customer_id={customer_id} order_id={order_id} payment_id={payment_id} amount={amount} message={data.get('message')}")
                    return self.return_message(success=False, message=data.get("message", "Insufficient balance"), data={"transaction_id": None})
                elif response.status_code == 500:
                    data = response.json()
                    logger.warning(f"Wallet entry failed with 500 | duplicate wallet entry | customer_id={customer_id} order_id={order_id} payment_id={payment_id} amount={amount} message={data.get('detail')}")
                    return self.return_message(success=False, message=data.get("detail", "Internal server error"), data={"transaction_id": None})
                else:
                    logger.error(f"Wallet entry failed: {response.status_code} - {response.text}")
                    return self.return_message(success=False, message=f"Wallet entry failed: {response.status_code}", data={"transaction_id": None})
        except httpx.TimeoutException:
            logger.error("Wallet service timeout during wallet entry")
            return self.return_message(success=False, message="Wallet service timeout", data={"transaction_id": None})
        except Exception as e:
            logger.error(f"Error adding wallet entry: {e}")
            return self.return_message(success=False, message=f"Wallet entry error: {str(e)}", data={"transaction_id": None})

    async def confirm_transaction(self, transaction_id: str) -> WalletServiceReturnMessage:
        """
        Confirm a held wallet transaction.
        Args:
            transaction_id: Transaction ID to confirm
        Returns:
            WalletServiceReturnMessage with confirmation result
        """
        self.url = f"{self.wallet_api_url}/confirm/{transaction_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, headers=self._get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    return self.return_message(success=True, message="Transaction confirmed successfully",
                        data={
                            "transaction_id": transaction_id,
                            "status": data.get("status", "confirmed")
                        }
                    )
                elif response.status_code == 404:
                    logger.warning(f"Transaction not found during confirmation | transaction_id={transaction_id}")
                    return self.return_message(success=False, message="Transaction not found", data={"transaction_id": transaction_id})
                else:
                    logger.error(f"Transaction confirmation failed: {response.status_code} - {response.text}")
                    return self.return_message(success=False, message=f"Confirmation failed: {response.status_code}", data={"transaction_id": transaction_id})
        except httpx.TimeoutException:
            logger.error("Wallet service timeout during confirmation")
            return self.return_message(success=False, message="Wallet service timeout", data={"transaction_id": transaction_id})
        except Exception as e:
            logger.error(f"Error confirming transaction: {e}")
            return self.return_message(success=False, message=f"Confirmation error: {str(e)}", data={"transaction_id": transaction_id})

    async def cancel_transaction(self, transaction_id: str) -> WalletServiceReturnMessage:
        """
        Cancel a held wallet transaction (release the hold).
        Args:
            transaction_id: Transaction ID to cancel
        Returns:
            WalletServiceReturnMessage with cancellation result
        """
        self.url = f"{self.wallet_api_url}/cancel/{transaction_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, headers=self._get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return self.return_message(success=True, message="Transaction cancelled successfully",
                        data={
                            "transaction_id": transaction_id,
                            "status": data.get("status", "cancelled")
                        }
                    )
                elif response.status_code == 404:
                    logger.warning(f"Transaction not found during cancellation | transaction_id={transaction_id}")
                    return self.return_message(success=False, message="Transaction not found", data={"transaction_id": transaction_id})
                else:
                    logger.error(f"Transaction cancellation failed: {response.status_code} - {response.text}")
                    return self.return_message(success=False, message=f"Cancellation failed: {response.status_code}", data={"transaction_id": transaction_id})
        except httpx.TimeoutException:
            logger.error("Wallet service timeout during cancellation")
            return self.return_message(success=False, message="Wallet service timeout", data={"transaction_id": transaction_id})
        except Exception as e:
            logger.error(f"Error cancelling transaction: {e}")
            return self.return_message(success=False, message=f"Cancellation error: {str(e)}", data={"transaction_id": transaction_id})

    async def redeem_gift_card(self, gift_card_number: str, user_id: str) -> WalletServiceReturnMessage:
        """
        Redeem a gift card through the wallet service.
        Args:
            gift_card_number: 12-digit alphanumeric gift card number
            user_id: User ID to credit the amount to
        Returns:
            WalletServiceReturnMessage with redemption result
        """
        url = f"{self.wallet_api_url}/internal/gift-cards/{gift_card_number}/redeem"
        payload = {
            "user_id": user_id
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"wallet_service_redeem_request | gift_card={gift_card_number} user={user_id}")

                response = await client.post(url, json=payload, headers=self._get_headers())
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"wallet_service_redeem_success | gift_card={gift_card_number} user={user_id} amount={result.get('amount_added')}")
                    return self.return_message(
                        success=True,
                        message="Gift card redeemed successfully",
                        data=result
                    )
                else:
                    error_json = response.json()
                    error_message = error_json.get('detail', response.text)
                    if error_message in ["Gift card already redeemed", "Invalid gift card format. Must be 12 alphanumeric characters."]:
                        suppress_error_logs = True
                        logger.warning(f"wallet_service_redeem_failed | gift_card={gift_card_number} user={user_id} status={response.status_code} error={error_message}")
                    else:
                        suppress_error_logs = False
                        logger.error(f"wallet_service_redeem_failed | gift_card={gift_card_number} user={user_id} status={response.status_code} error={error_message}")
                    return self.return_message(
                        success=False,
                        message=error_message,
                        data={"gift_card_number": gift_card_number},
                        suppress_error_logs=suppress_error_logs
                    )

        except httpx.TimeoutException:
            logger.error(f"wallet_service_timeout | gift_card={gift_card_number} user={user_id}")
            return self.return_message(
                success=False,
                message="Wallet service timeout",
                data={"gift_card_number": gift_card_number}
            )
        except Exception as e:
            logger.error(f"wallet_service_request_error | gift_card={gift_card_number} user={user_id} error={str(e)}")
            return self.return_message(
                success=False,
                message=f"Wallet service request failed: {str(e)}",
                data={"gift_card_number": gift_card_number}
            )

    async def validate_gift_card(self, gift_card_number: str) -> WalletServiceReturnMessage:
        """
        Validate a gift card through the wallet service.
        Args:
            gift_card_number: 12-digit alphanumeric gift card number
        Returns:
            WalletServiceReturnMessage with validation result
        """
        url = f"{self.wallet_api_url}/api/gift-cards/validate"
        payload = {
            "gift_card_number": gift_card_number
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"wallet_service_validate_request | gift_card={gift_card_number}")

                response = await client.post(url, json=payload, headers=self._get_headers())

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"wallet_service_validate_success | gift_card={gift_card_number} valid={result.get('valid')}")
                    return self.return_message(
                        success=True,
                        message="Gift card validation completed",
                        data=result
                    )
                else:
                    error_detail = response.text
                    logger.error(f"wallet_service_validate_failed | gift_card={gift_card_number} status={response.status_code} error={error_detail}")
                    return self.return_message(
                        success=False,
                        message=f"Gift card validation failed: {error_detail}",
                        data={"gift_card_number": gift_card_number}
                    )
 
        except httpx.TimeoutException:
            logger.error(f"wallet_service_validate_timeout | gift_card={gift_card_number}")
            return self.return_message(
                success=False,
                message="Wallet service timeout",
                data={"gift_card_number": gift_card_number}
            )
        except Exception as e:
            logger.error(f"wallet_service_validate_request_error | gift_card={gift_card_number} error={str(e)}")
            return self.return_message(
                success=False,
                message=f"Wallet service request failed: {str(e)}",
                data={"gift_card_number": gift_card_number}
            )

    async def get_gift_card_details(self, gift_card_number: str) -> WalletServiceReturnMessage:
        """
        Get gift card details through the wallet service.
        Args:
            gift_card_number: 12-digit alphanumeric gift card number
        Returns:
            WalletServiceReturnMessage with gift card details
        """
        url = f"{self.wallet_api_url}/api/gift-cards/{gift_card_number}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"wallet_service_details_request | gift_card={gift_card_number}")

                response = await client.get(url, headers=self._get_headers())
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"wallet_service_details_success | gift_card={gift_card_number}")
                    return self.return_message(
                        success=True,
                        message="Gift card details retrieved successfully",
                        data=result
                    )
                elif response.status_code == 404:
                    logger.warning(f"wallet_service_gift_card_not_found | gift_card={gift_card_number}")
                    return self.return_message(
                        success=False,
                        message="Gift card not found",
                        data={"gift_card_number": gift_card_number}
                    )
                else:
                    error_detail = response.text
                    logger.error(f"wallet_service_details_failed | gift_card={gift_card_number} status={response.status_code} error={error_detail}")
                    return self.return_message(
                        success=False,
                        message=f"Gift card details request failed: {error_detail}",
                        data={"gift_card_number": gift_card_number}
                    )

        except httpx.TimeoutException:
            logger.error(f"wallet_service_details_timeout | gift_card={gift_card_number}")
            return self.return_message(
                success=False,
                message="Wallet service timeout",
                data={"gift_card_number": gift_card_number}
            )
        except Exception as e:
            logger.error(f"wallet_service_details_request_error | gift_card={gift_card_number} error={str(e)}")
            return self.return_message(
                success=False,
                message=f"Wallet service request failed: {str(e)}",
                data={"gift_card_number": gift_card_number}
            )
