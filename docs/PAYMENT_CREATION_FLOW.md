# 📄 Payments on Order Creation – Rozana OMS

This document explains how payments are validated, created, and processed when an order is created in the OMS, for all payment modes and both origins (App/POS). It is based on the current implementation in:

- `application/app/core/order_functions.py#create_order_core`
- `application/app/validations/payment_validations.py#PaymentValidator`
- `application/app/core/payment_defaults.py#PaymentDefaults`
- `application/app/services/payments/payment_processor.py#OrderPaymentProcessor`
- `application/app/integrations/razorpay_service.py#RazorpayService`

## Quick Reference

### Allowed modes by origin

| Origin | Modes |
|--------|-------|
| App    | `cod`, `razorpay`, `wallet` |
| POS    | `cash`, `razorpay`, `wallet` |

### create_payment_order rules
- Razorpay: true
- Wallet: true
- Cash, COD: false

### Initial status by mode

| Mode | Status |
|------|--------|
| cash | COMPLETED (51) |
| cod | PENDING (50) |
| razorpay | PENDING (50) |
| wallet | PENDING (50) |

### What happens at creation (processing & sync)

App (origin = `app`)

| Modes | What we do right now | WMS sync now? |
|-------|-----------------------|---------------|
| COD | No payment processing | Yes |
| RP | Create RP order; no settlement yet | No |
| RP + Wallet | Create RP order; Wallet NOT debited now | No |
| Wallet only | Debit wallet immediately | Yes |

POS (origin = `pos`)

| Modes | What we do right now | WMS sync now? |
|-------|-----------------------|---------------|
| Cash | Mark payment COMPLETED (51) | Yes |
| Wallet | Debit wallet immediately | Yes |
| Cash + Wallet | Cash COMPLETE, Wallet debited | Yes |
| Any combo with RP | RP present → other parts deferred | No |

Notes
- If any Razorpay part exists, other parts are deferred at creation; order sync waits for RP completion.
- If no Razorpay: wallet is debited now (if present) and cash is completed now; order sync proceeds.

#### Sync rules (all cases)

| Origin | Modes | Sync timing | Sync trigger |
|--------|-------|-------------|--------------|
| App | COD | Immediate | After creating payments (no processing needed) |
| App | Wallet only | Immediate | After wallet debit succeeds in `OrderPaymentProcessor.process_order_payment()` |
| App | RP | Deferred | When RP payment is verified and all payments are COMPLETED via `update_existing_payment()` |
| App | RP + Wallet | Deferred | When RP payment is verified; process wallet then ensure all parts COMPLETED |
| POS | Cash | Immediate | After cash marked COMPLETED in `OrderPaymentProcessor` |
| POS | Wallet | Immediate | After wallet debit succeeds in `OrderPaymentProcessor` |
| POS | Cash + Wallet | Immediate | After cash COMPLETE and wallet debit succeeds in `OrderPaymentProcessor` |
| POS | Any combo with RP | Deferred | When RP payment is verified and all payments are COMPLETED |

Sync mechanics
- Immediate sync: `OrderPaymentProcessor.process_order_payment` returns `sync_order=True`, then `create_order_core` enqueues `PotionsService.sync_order_by_id`.
- Deferred sync: `sync_order=False` at creation (RP present). Sync happens after payment completion path updates statuses to COMPLETED (51) for all parts.


### Minimal flow
1) Validate items + payment rules
2) Create order
3) For each payment: create DB record (and Razorpay order if mode=razorpay)
4) Process now: wallet debit, cash complete; if Razorpay present → defer
5) Sync if no Razorpay and processing succeeded

---
Behavioral notes
- If any Razorpay part exists at creation, other parts are not settled at this step and order sync is deferred.
- COD-only orders sync to WMS with payment status PENDING (50).
- Wallet-only orders are debited immediately; failures abort the flow.
- POS cash is marked COMPLETED (51) immediately.
---


### Payment Status Transitions

| Status Transition | Trigger | Notes |
|-------------------|---------|-------|
| **PENDING (50) → COMPLETED (51)** | - Wallet: After successful debit | For Razorpay, handled by [update_existing_payment()] |
|  | - Cash: Immediately at POS |  |
|  | - Razorpay: After successful verification |  |
| **PENDING (50) → FAILED (52)** | - Wallet: Insufficient balance | Triggers order cancellation if no other successful payments |
|  | - Razorpay: Payment verification fails |  |
| **COMPLETED (51) → REFUNDED (53)** | - Order return/refund processed | Handled by `RefundProcessor` |


#### Partial Payment Failures
- If wallet debit fails while other payments succeed, the entire order is rolled back
- For Razorpay + Wallet combinations, wallet is only debited after Razorpay payment succeeds

### Webhook Processing

####   Razorpay Webhook (`/webhooks/razorpay`)
- **Verification**: Validates webhook signature
- **Status Update**: Changes payment status to COMPLETED
- **Additional Processing**: Triggers [process_razorpay_included_order_payment()] for any pending wallet/cash payments
- **Order Sync**: Syncs order to WMS when all payments complete successfully
