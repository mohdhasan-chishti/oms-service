"""
Paytm POS Sale API service for terminal-based payments in the OMS system.

This module provides the interface for Paytm POS Sale API integration,
including payment initiation, status checking, and payment confirmation.

Paytm POS Sale Integration Flow:
1. POS initiates payment request to backend with terminal ID
2. Backend calls Paytm POS Sale API (/ecr/payment/request)
3. EDC terminal at store processes payment (customer interaction)
4. POS polls backend for payment status
5. Backend confirms payment and updates order status
"""

import requests
import json
import re
import uuid
from typing import Dict, Any
from decimal import Decimal
from app.models.common import get_ist_now
from app.utils.datetime_helpers import format_datetime_readable

# Official Paytm checksum library
from paytmchecksum import PaytmChecksum

# Repository
from app.repository.facility_terminal import FacilityTerminalRepository

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("paytm_service")

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()


class PaytmService:
    """Service class for Paytm POS Sale API terminal integration"""
    
    def __init__(self, terminal_id: str = None):
        self.terminal_id = terminal_id
        self.integration_enabled = configs.PAYTM_INTEGRATION_ENABLED
        self.base_url = configs.PAYTM_BASE_URL
        self.timeout = configs.PAYTM_TIMEOUT
        self.channel_id = configs.PAYTM_CHANNEL_ID or "EDC"
        
        self.merchant_id, self.merchant_key = self._get_credentials()

        # Derive PG base host for Refund APIs from ECR base
        if "securegw-stage.paytm.in" in (self.base_url or ""):
            self.pg_base = "https://securegw-stage.paytm.in"
        else:
            self.pg_base = "https://securegw.paytm.in"

        if not self.integration_enabled:
            logger.warning("Paytm integration is disabled")
            return

        if not self.merchant_id or not self.merchant_key:
            logger.error("Paytm merchant ID and merchant key are required")
            raise ValueError("Paytm merchant ID and merchant key are required")

        logger.info(f"paytm_service_initialized | merchant_id={self.merchant_id}")

    def _get_credentials(self) -> tuple:
        """Get merchant credentials from terminal config or fallback to .env"""
        merchant_id = configs.PAYTM_MERCHANT_ID
        merchant_key = configs.PAYTM_MERCHANT_KEY
        
        if self.terminal_id:
            try:
                repo = FacilityTerminalRepository()
                creds = repo.get_terminal_credentials(self.terminal_id)
                if creds.get('merchant_id') and creds.get('merchant_key'):
                    merchant_id = creds['merchant_id']
                    merchant_key = creds['merchant_key']
            except Exception as e:
                logger.warning(f"Failed to fetch terminal credentials | terminal_id={self.terminal_id} error={e}")
        
        return merchant_id, merchant_key

    def _generate_checksum(self, body: Dict[str, Any]) -> str:
        """
        Generate checksum for Paytm POS Sale API using official Paytm library.
        
        Uses PaytmChecksum.generateSignature() from paytmchecksum package.
        
        Args:
            body: Request body dictionary (flat key-value pairs only)
            
        Returns:
            Checksum string
        """
        try:
            logger.debug(f"checksum_body | {body}")

            # Generate checksum using official Paytm library
            checksum = PaytmChecksum.generateSignature(body, self.merchant_key)
            logger.debug(f"checksum_generated | checksum={checksum}")
            return checksum
        except Exception as e:
            logger.error(f"checksum_generation_error | error={e}", exc_info=True)
            raise

    def _generate_pg_signature(self, body: Dict[str, Any]) -> str:
        """
        Generate signature for Paytm PG APIs (Refund, Refund Status) over the compact JSON string of body.
        """
        body_str = json.dumps(body, separators=(',', ':'))
        try:
            sig = PaytmChecksum.generateSignature(body_str, self.merchant_key)
            return sig
        except Exception as e:
            logger.error(f"pg_signature_generation_error | error={e}", exc_info=True)
            raise

    @staticmethod
    def _parse_json_with_trailing_commas(text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            cleaned = re.sub(r",(\s*[}\]])", r"\1", text)
            return json.loads(cleaned)

    async def initiate_payment(self, order_id: str, amount: Decimal, terminal_id: str) -> Dict[str, Any]:
        """
        Initiate payment on Paytm EDC terminal using POS Sale API.
        Calls: POST https://securegw-stage.paytm.in/ecr/payment/request
        Args:
            order_id: Merchant reference number (displayed on device)
            amount: Payment amount in rupees
            terminal_id: EDC terminal ID (uses default if not provided)
        Returns:
            Dict with success status and payment details
        """
        if not self.integration_enabled:
            logger.info(f"paytm_payment_skipped | order_id={order_id}")
            return {"success": False, "message": "Paytm integration is disabled"}

        try:
            txn_id = f"{order_id}{uuid.uuid4().hex[:8].upper()}"
            amount_paise = int(amount * 100)

            # Get timestamp
            now = get_ist_now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

            # Build request body (only key-value pairs, no nested objects)
            body = {
                "paytmMid": self.merchant_id,
                "paytmTid": terminal_id,
                "transactionDateTime": timestamp,
                "merchantTransactionId": txn_id,
                "merchantReferenceNo": order_id,
                "transactionAmount": str(amount_paise)
            }

            # Generate checksum
            checksum = self._generate_checksum(body)
            # Build complete request
            request_payload = {
                "head": {
                    "requestTimeStamp": timestamp,
                    "channelId": self.channel_id,
                    "checksum": checksum,
                    "version": "3.1"
                },
                "body": body
            }

            logger.info(f"paytm_payment_initiating | order_id={order_id} txn_id={txn_id} amount={amount} terminal_id={terminal_id}")
            logger.info(f"paytm_payment_initiating | request_payload={request_payload} | order_id={order_id}")

            # Call Paytm API
            api_url = f"{self.base_url}/payment/request"
            response = requests.post(api_url, json=request_payload, timeout=self.timeout)

            response.raise_for_status()
            result = response.json()

            # Parse response
            resp_body = result.get("body", {})
            result_info = resp_body.get("resultInfo", {})
            result_status = result_info.get("resultStatus", "")
            result_code = result_info.get("resultCode", "")
            result_msg = result_info.get("resultMsg", "")

            # Handle failure
            if result_status == "F":
                logger.error(f"paytm_payment_failed | order_id={order_id} code={result_code} msg={result_msg}")
                return {
                    "success": False,
                    "error": result_msg,
                    "result_code": result_code,
                    "result_code_id": result_info.get("resultCodeId")
                }

            logger.info(f"paytm_payment_initiated | order_id={order_id} txn_id={txn_id}")
            
            return {
                "success": True,
                "txn_id": txn_id,
                "order_id": order_id,
                "amount": float(amount),
                "amount_paise": amount_paise,
                "terminal_id": terminal_id,
                "status": "INITIATED",
                "result_code": result_code,
                "message": result_msg,
                "created_at": format_datetime_readable(now)
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"paytm_payment_request_error | order_id={order_id} error={e}", exc_info=True)
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"paytm_payment_error | order_id={order_id} error={e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def check_payment_status(self, txn_id: str, order_id: str, terminal_id: str) -> Dict[str, Any]:
        """
        Check payment status from Paytm
        Args:
            txn_id: Transaction ID
            order_id: Order ID
            terminal_id: EDC terminal ID (required)
        Returns:
            Dict containing payment status details
        """
        if not self.integration_enabled:
            logger.warning(f"paytm_status_check_skipped | txn_id={txn_id}")
            return {
                "success": False,
                "skipped": True,
                "message": "Paytm integration is disabled"
            }

        try:
            # Timestamp and terminal id
            now = get_ist_now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

            # Build body for POS Status Enquiry API
            body = {
                "paytmMid": self.merchant_id,
                "paytmTid": terminal_id,
                "transactionDateTime": timestamp,
                "merchantTransactionId": txn_id
            }

            # Generate checksum on body as per Paytm docs
            checksum = self._generate_checksum(body)

            request_payload = {
                "head": {
                    "requestTimeStamp": timestamp,
                    "channelId": self.channel_id,
                    "checksum": checksum,
                    "version": "3.1"
                },
                "body": body
            }

            logger.info(f"paytm_status_checking | txn_id={txn_id} order_id={order_id}")
            logger.info(f"paytm_status_checking | request_payload={request_payload}")

            response = requests.post(f"{self.base_url}/V2/payment/status", json=request_payload, timeout=self.timeout)
            response.raise_for_status()

            # Try JSON first; fallback to tolerant parser if needed
            try:
                result = response.json()
            except ValueError:
                result = self._parse_json_with_trailing_commas(response.text)

            resp_body = result.get("body", result)
            result_info = resp_body.get("resultInfo", {})
            status = result_info.get("resultStatus")

            # Determine success based on payment status
            is_success = status in ["SUCCESS", "CAPTURED"]
            logger.info(f"paytm_status_retrieved | txn_id={txn_id} order_id={order_id} status={status} success={is_success}")
            logger.info(f"paytm_status_retrieved | order_id={order_id} result={result}")

            return {
                "success": is_success,
                "txn_id": txn_id,
                "order_id": order_id,
                "status": status,
                "message": result_info.get("resultMsg", resp_body.get("RESPMSG", "")),
                "paytm_response": result
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"paytm_status_check_request_error | txn_id={txn_id} error={e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to check Paytm payment status"
            }
        except ValueError as e:
            # JSON parsing error
            logger.error(f"paytm_status_check_json_error | txn_id={txn_id} error={e} response_text={response.text if 'response' in locals() else 'N/A'}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "response_text": response.text if 'response' in locals() else None,
                "message": "Failed to parse Paytm response - invalid JSON"
            }
        except Exception as e:
            logger.error(f"paytm_status_check_error | txn_id={txn_id} error={e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to check Paytm payment status"
            }
