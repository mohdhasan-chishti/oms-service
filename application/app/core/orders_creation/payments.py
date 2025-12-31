"""
Payment creation and gateway functions
"""
import secrets
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple

from fastapi import HTTPException

from app.services.payment_service import PaymentService
from app.repository.payments import PaymentRepository
from app.integrations.razorpay_service import RazorpayService
from app.integrations.cashfree_service import CashfreeService
from app.integrations.paytm_service import PaytmService
from app.logging.utils import get_app_logger

logger = get_app_logger("app.core.orders_creation.payments")


class PaymentProcessor:
    """Handles payment processing orchestration for orders"""

    def __init__(self):
        self.payment_service = PaymentService()
        self.payment_repository = PaymentRepository()

    async def handle_order_payments(self, order, created_orders: List[Dict], user_phone_number: str, parent_order_id: str) -> Tuple[List[Dict], Dict]:
        """
        Process all payment steps for orders:
        1. Calculate payment allocations
        2. Prepare customer details
        3. Create payment records
        4. Create gateway orders

        Returns: (all_payment_records, primary_payment_records)
        """
        # Calculate payment allocations
        payment_ids, payment_allocations = calculate_payment_allocations(payments=order.payment, created_orders=created_orders)

        # Prepare customer details
        customer_details = {"customer_id": order.customer_id, "customer_name": order.customer_name or order.address.full_name, "customer_phone": user_phone_number}

        # Create payment records for all orders
        all_payment_records, primary_payment_records = await create_payment_records_for_orders(payments=order.payment, created_orders=created_orders, payment_ids=payment_ids, payment_allocations=payment_allocations)

        # Create payment gateway orders
        all_payment_records = await create_gateway_orders(payments=order.payment, created_orders=created_orders, all_payment_records=all_payment_records, customer_details=customer_details, parent_order_id=parent_order_id)

        return all_payment_records, primary_payment_records


def calculate_payment_allocations(payments: List, created_orders: List[Dict]) -> Tuple[Dict, Dict]:
    """
    Calculate payment allocations across orders
    
    For single facility: Each payment maps to full amount
    For multi-facility: Payments are split proportionally by order amount
    
    Returns: (payment_ids, payment_allocations)
    """
    # Generate unique payment IDs for each payment mode
    payment_ids = {}
    for payment in payments:
        payment_ids[payment.payment_mode.lower()] = f"{payment.payment_mode.upper()}_{secrets.token_hex(4).upper()}"
    
    # Calculate total order amount
    total_order_amount = sum(Decimal(str(order['total_amount'])) for order in created_orders)
    if total_order_amount <= 0:
        return payment_ids, {}
    
    # Get payment modes and amounts
    payment_modes = []
    for payment in payments:
        payment_modes.append(payment.payment_mode.lower())
    payment_amounts = []
    for payment in payments:
        payment_amounts.append(Decimal(str(payment.amount)))
    total_payment = sum(payment_amounts)
    
    if total_payment <= 0:
        return payment_ids, {}
    
    # Calculate ratios for each payment method
    payment_ratios = []
    for payment_amount in payment_amounts:
        payment_ratios.append(payment_amount / total_payment)
    
    # Allocate payments to each order
    allocations = {}
    for order in created_orders:
        order_id = order['order_id']
        order_total = Decimal(str(order['total_amount']))
        allocations[order_id] = {}
        
        for i, mode in enumerate(payment_modes):
            amount = (order_total * payment_ratios[i]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            allocations[order_id][mode] = amount
    
    logger.info(f"Payment allocations calculated for {len(created_orders)} orders")
    return payment_ids, allocations


async def create_payment_records_for_orders(payments: List, created_orders: List[Dict], payment_ids: Dict, payment_allocations: Dict) -> Tuple[List[Dict], Dict]:
    """
    Create payment records for all orders
    
    Returns: (all_payment_records, primary_payment_records)
    """
    payment_service = PaymentService()
    payment_repository = PaymentRepository()
    all_payment_records = []
    payment_total_amount = sum(Decimal(str(payment.amount)) for payment in payments)
    
    is_multi_facility = len(created_orders) > 1
    
    # Create payment records for ALL orders
    for order_data in created_orders:
        for payment in payments:
            # Determine payment amount
            if is_multi_facility:
                payment_mode_lower = payment.payment_mode.lower()
                allocated_amount = payment_allocations[order_data['order_id']].get(payment_mode_lower, Decimal('0'))
                if allocated_amount <= 0:
                    continue
                payment_amount = allocated_amount
            else:
                payment_amount = Decimal(str(payment.amount))
            
            terminal_id = getattr(payment, "terminal_id", None)
            payment_record = await payment_service.create_payment_record(
                internal_order_id=order_data['internal_order_id'],
                payment_amount=payment_amount,
                payment_mode=payment.payment_mode,
                total_amount=Decimal(str(payment_total_amount)),
                payment_order_id="",
                terminal_id=terminal_id,
            )
            
            # Update to shared payment_id for multi-facility
            if is_multi_facility:
                shared_payment_id = payment_ids[payment_mode_lower]
                payment_repository.upadate_the_razorpay_payment_id(payment_record['payment_record_id'], shared_payment_id)
                payment_record['payment_id'] = shared_payment_id
            
            all_payment_records.append(payment_record)
    
    primary_payment_records = []
    for payment_record in all_payment_records:
        if payment_record['order_id'] == created_orders[0]['internal_order_id']:
            primary_payment_records.append(payment_record)
    
    logger.info(f"Created {len(all_payment_records)} payment records for {len(created_orders)} orders")
    
    return all_payment_records, primary_payment_records


async def create_gateway_orders(payments: List, created_orders: List[Dict], all_payment_records: List[Dict], customer_details: Dict, parent_order_id: str) -> List[Dict]:
    """
    Create payment gateway orders (Razorpay, Cashfree, Paytm)
    
    Extracts amount and payment_id from all_payment_records and passes to gateway functions
    Updates ALL payment records with gateway order IDs
    
    Returns: Updated all_payment_records
    """
    for payment in payments:
        payment_mode = payment.payment_mode.lower()

        # Get total amount from database records for this payment mode
        amount_to_pay = Decimal('0')
        for payment_record in all_payment_records:
            if payment_record.get("payment_mode") == payment_mode:
                # Sum up amounts
                amount_to_pay += Decimal(str(payment_record.get("database_payment_amount", 0)))

        logger.info(f"Gateway order creation | mode={payment_mode} | database_amount={amount_to_pay}")

        # Create Razorpay order
        if payment_mode == "razorpay":
            all_payment_records = await create_razorpay_order(payment, created_orders, all_payment_records, customer_details, parent_order_id, amount_to_pay)

        # Create Cashfree order
        elif payment_mode == "cashfree":
            all_payment_records = await create_cashfree_order(payment, created_orders, all_payment_records, customer_details, parent_order_id, amount_to_pay)

        # Initiate Paytm POS
        elif payment_mode == "paytm_pos":
            all_payment_records = await create_paytm_pos_order(payment, created_orders, all_payment_records, parent_order_id, amount_to_pay)

    return all_payment_records


async def create_razorpay_order(payment, created_orders: List[Dict], all_payment_records: List[Dict], customer_details: Dict, parent_order_id: str, amount_to_pay: Decimal) -> List[Dict]:
    """Create Razorpay payment order and update payment records"""
    payment_repository = PaymentRepository()

    # Prepare notes for gateway
    all_order_ids = [created_order['order_id'] for created_order in created_orders]

    razorpay_service = RazorpayService()

    # Build notes
    notes = {"parent_order_id": parent_order_id, "order_ids": ",".join(all_order_ids)}

    razorpay_result = await razorpay_service.create_razorpay_order(order_id=parent_order_id,
        amount=amount_to_pay,
        customer_details=customer_details,
        notes=notes
    )

    razorpay_order_id = razorpay_result["razorpay_order_id"]
    logger.info(f"Razorpay order created | parent_order_id={parent_order_id} | razorpay_order_id={razorpay_order_id} | amount={amount_to_pay}")

    # Update ALL payment records with razorpay order id
    for payment_record in all_payment_records:
        if payment_record["payment_mode"] == "razorpay":
            payment_repository.update_the_razorpay_order_id(id=payment_record["payment_record_id"], razorpay_order_id=razorpay_order_id)
            payment_record["payment_order_id"] = razorpay_order_id

    return all_payment_records


async def create_cashfree_order(payment, created_orders: List[Dict], all_payment_records: List[Dict], customer_details: Dict, parent_order_id: str, amount_to_pay: Decimal) -> List[Dict]:
    """Create Cashfree payment order and update payment records"""
    payment_repository = PaymentRepository()

    # Prepare notes for gateway
    all_order_ids = [created_order['order_id'] for created_order in created_orders]

    cashfree_service = CashfreeService()

    # Build notes
    notes = {"parent_order_id": parent_order_id, "order_ids": ",".join(all_order_ids)}

    cashfree_result = cashfree_service.create_order(
        order_id=parent_order_id,
        amount=amount_to_pay,
        customer_details=customer_details,
        customer_phone=customer_details.get("customer_phone"),
        customer_email=customer_details.get("customer_email"),
        notes=notes
    )

    cashfree_order_id = cashfree_result.get("cf_order_id")
    if cashfree_order_id is None:
        raise HTTPException(status_code=400, detail="Failed to create Cashfree order - missing cf_order_id")

    cashfree_order_id_str = str(cashfree_order_id)
    logger.info(f"Cashfree order created | parent_order_id={parent_order_id} | cf_order_id={cashfree_order_id_str} | amount={amount_to_pay}")

    # Update ALL payment records with cashfree order id
    for payment_record in all_payment_records:
        if payment_record["payment_mode"] == "cashfree":
            payment_repository.update_the_razorpay_order_id(id=payment_record["payment_record_id"], razorpay_order_id=parent_order_id)
            payment_record["payment_order_id"] = cashfree_order_id_str
            payment_record["cf_order_id"] = cashfree_order_id_str
            payment_record["payment_url"] = cashfree_result.get("payment_url")
            payment_record["payment_session_id"] = cashfree_result.get("payment_session_id")
            payment_record["order_status"] = cashfree_result.get("order_status")

    return all_payment_records


async def create_paytm_pos_order(payment, created_orders: List[Dict], all_payment_records: List[Dict], parent_order_id: str, amount_to_pay: Decimal) -> List[Dict]:
    """Initiate Paytm POS payment and update payment records"""
    payment_repository = PaymentRepository()
    primary_order_id = created_orders[0]['order_id']

    terminal_id = getattr(payment, "terminal_id", None)
    paytm_service = PaytmService(terminal_id=terminal_id)
    paytm_result = await paytm_service.initiate_payment(order_id=primary_order_id, amount=amount_to_pay, terminal_id=terminal_id)

    if not paytm_result.get("success"):
        logger.error(f"paytm_pos_initiate_failed | order_id={primary_order_id} error={paytm_result.get('error')}")
        raise HTTPException(status_code=400, detail=paytm_result.get("error", "Failed to initiate Paytm POS payment"))

    txn_id = paytm_result.get("txn_id")
    logger.info(f"Paytm POS initiated | parent_order_id={parent_order_id} | txn_id={txn_id} | amount={amount_to_pay}")

    # Update ALL payment records with paytm txn id
    for payment_record in all_payment_records:
        if payment_record["payment_mode"] == "paytm_pos":
            payment_repository.update_the_razorpay_order_id(id=payment_record["payment_record_id"], razorpay_order_id=txn_id)
            payment_record["payment_order_id"] = txn_id
            payment_record["paytm_txn_id"] = txn_id

    return all_payment_records



