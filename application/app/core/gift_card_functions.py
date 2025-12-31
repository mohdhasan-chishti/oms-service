"""
Core gift card functions for handling gift card operations.
This module contains the main business logic for gift card redemption and validation.
"""

from typing import Dict, Any
from decimal import Decimal

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("gift_card_core")

# Services
from app.integrations.wallet_service import WalletService

# DTOs
from app.dto.gift_card import (
    GiftCardRedeemRequest,
    GiftCardRedeemResponse,
    GiftCardValidateRequest,
    GiftCardValidateResponse
)


async def redeem_gift_card_core(gift_card_number: str, request: GiftCardRedeemRequest, channel: str) -> GiftCardRedeemResponse:
    """
    Core function for gift card redemption.
    Args:
        gift_card_number: 12-digit alphanumeric gift card number
        request: Gift card redemption request
        channel: Channel (app/pos) for tracking
    Returns:
        GiftCardRedeemResponse with redemption result

    Raises:
        WalletServiceError: If redemption fails
    """
    logger.info(f"gift_card_redeem_start | gift_card={gift_card_number} user={request.user_id} channel={channel}")
    
    try:
        # Initialize wallet service
        wallet_service = WalletService()

        # Redeem gift card through wallet service
        redemption_result = await wallet_service.redeem_gift_card(gift_card_number=gift_card_number, user_id=request.user_id)

        # Extract data from wallet service response
        if redemption_result.success:
            data = redemption_result.data or {}
            response = GiftCardRedeemResponse(
                success=True,
                message=redemption_result.message,
                amount_added=data.get("amount_added"),
                new_wallet_balance=data.get("new_wallet_balance"),
                gift_card_number=gift_card_number
            )
            logger.info(f"gift_card_redeem_success | gift_card={gift_card_number} user={request.user_id} channel={channel} amount={response.amount_added}")
        else:
            response = GiftCardRedeemResponse(
                success=False,
                message=redemption_result.message,
                amount_added=None,
                new_wallet_balance=None,
                gift_card_number=gift_card_number
            )
            if redemption_result.suppress_error_logs:
                logger.warning(f"gift_card_redeem_failed | gift_card={gift_card_number} user={request.user_id} channel={channel} error={redemption_result.message}")
            else:
                logger.error(f"gift_card_redeem_failed | gift_card={gift_card_number} user={request.user_id} channel={channel} error={redemption_result.message}")

        return response
        
    except Exception as e:
        logger.error(f"gift_card_redeem_exception | gift_card={gift_card_number} user={request.user_id} channel={channel} error={str(e)}")
        return GiftCardRedeemResponse(
            success=False,
            message="Gift card redemption failed due to internal error",
            amount_added=None,
            new_wallet_balance=None,
            gift_card_number=gift_card_number
        )


async def validate_gift_card_core(request: GiftCardValidateRequest, channel: str) -> GiftCardValidateResponse:
    """
    Core function for gift card validation.
    Args:
        request: Gift card validation request
        channel: Channel (app/pos) for tracking
    Returns:
        GiftCardValidateResponse with validation result
        
    Raises:
        WalletServiceError: If validation fails
    """
    logger.info(f"gift_card_validate_start | gift_card={request.gift_card_number} channel={channel}")

    try:
        # Initialize wallet service
        wallet_service = WalletService()

        # Validate gift card through wallet service
        validation_result = await wallet_service.validate_gift_card(gift_card_number=request.gift_card_number)

        # Extract data from wallet service response
        if validation_result.success:
            data = validation_result.data or {}
            response = GiftCardValidateResponse(
                valid=data.get("valid", False),
                gift_card_number=request.gift_card_number,
                amount=data.get("amount"),
                status=data.get("status"),
                status_description=data.get("status_description"),
                expires_at=data.get("expires_at"),
                message=validation_result.message
            )
        else:
            response = GiftCardValidateResponse(
                valid=False,
                gift_card_number=request.gift_card_number,
                amount=None,
                status=None,
                status_description=None,
                expires_at=None,
                message=validation_result.message
            )
        
        logger.info(f"gift_card_validate_success | gift_card={request.gift_card_number} channel={channel} valid={response.valid}")
        return response
        
    except Exception as e:
        logger.error(f"gift_card_validate_exception | gift_card={request.gift_card_number} channel={channel} error={str(e)}")
        return GiftCardValidateResponse(
            valid=False,
            gift_card_number=request.gift_card_number,
            amount=None,
            status=None,
            status_description=None,
            expires_at=None,
            message="Gift card validation failed due to internal error"
        )


async def get_gift_card_details_core(gift_card_number: str, channel: str) -> Dict[str, Any]:
    """
    Core function for getting gift card details.
    Args:
        gift_card_number: 12-digit alphanumeric gift card number
        channel: Channel (app/pos) for tracking
    Returns:
        Dict containing gift card details
    Raises:
        WalletServiceError: If request fails
    """
    logger.info(f"gift_card_details_start | gift_card={gift_card_number} channel={channel}")

    try:
        # Initialize wallet service
        wallet_service = WalletService()

        # Get gift card details through wallet service
        details_result = await wallet_service.get_gift_card_details(gift_card_number=gift_card_number)
        if details_result.success:
            logger.info(f"gift_card_details_success | gift_card={gift_card_number} channel={channel}")
            return details_result.data
        else:
            logger.error(f"gift_card_details_failed | gift_card={gift_card_number} channel={channel} error={details_result.message}")
            raise Exception(details_result.message)

    except Exception as e:
        logger.error(f"gift_card_details_exception | gift_card={gift_card_number} channel={channel} error={str(e)}")
        raise e
