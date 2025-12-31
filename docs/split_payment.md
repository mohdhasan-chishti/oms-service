# **📄 Split Payments – Rozana OMS**

### **1. Accepted Payment Modes by Origin**

| **Origin** | **Allowed modes**                        |
|------------|------------------------------------------|
| App        | cod, razorpay, wallet                    |
| POS        | cash, razorpay, wallet                   |

### **2. Valid Split Combinations**

| **Origin** | **Single-mode allowed** | **Max modes** | **Allowed two-mode combos** | **Notes** |
|----|----|----|----|----|
| App | Yes | 2 | razorpay + wallet | No duplicates; amounts must sum to order total |
| POS | Yes | No explicit limit | All combinations allowed | No duplicates; amounts must sum to order total |

### **3. create_payment_order Requirements (at order creation)**

| **Mode** | **create_payment_order** | **Source / Notes** |
|----|----|----|
| razorpay | true | DTO PaymentInfo.validate_create_payment_order; service validator permits |
| cash | false | DTO enforces false |
| cod | false | Service validator only allows create_payment_order for razorpay/wallet |
| wallet | true | Enforced in DTO (`PaymentInfo.validate_create_payment_order`) |

### **4. Initial Payment Status by Mode**

| **Mode** | **Initial status** |
|----------|--------------------|
| cash     | COMPLETED          |
| cod      | PENDING            |
| razorpay | PENDING            |
| wallet   | PENDING            |

### **5. Payment Status Constants**

| **Status** | **Code** | **Description**   |
|------------|----------|-------------------|
| PENDING    | 50       | Payment Pending   |
| COMPLETED  | 51       | Payment Completed |
| FAILED     | 52       | Payment Failed    |
| REFUNDED   | 53       | Payment Refunded  |

### **6. App Payment Endpoints**

| **Method** | **Path** | **Purpose** |
|----|----|----|
| POST | /app/v1/create_payment_order | Create Razorpay order |
| POST | /app/v1/verify_payment | Verify Razorpay payment and update record |
| GET | /app/v1/payment_status/{order_id} | Payment summary for an order |

### **7. Order Creation Flow (with Split Payments)**

1. **Authentication**
   - Verify user/session (e.g., JWT/API key) before processing the request.

2. **Order payload validation**
   - Validate items, quantities, taxes, and totals.
   - Ensure total amount matches the sum of line items (see `OrderCreateValidator.validate_total_amount`).

3. **Payment input validation**
   - Validate `origin`-based allowed modes and split rules (max 2 modes, no duplicates, min amounts).
   - Enforce `create_payment_order` rules:
     - Razorpay: `true`
     - Cash/COD: `false`
     - Wallet: `true`
   - Use `PaymentInfo` and service validators to enforce rules.

4. **Wallet pre-checks (if wallet used)**
   - Check or create wallet for the customer.
   - Validate sufficient wallet balance for the wallet amount.

5. **Create order + payment records**
   - Create the order and associated `payment_details` entries for each split component with initial statuses (Cash: COMPLETED; others: PENDING).

6. **Trigger payment processing**
   - Razorpay present: create Razorpay order and return its details to client.
   - Wallet present: enqueue background task to debit wallet and update status.

7. **Verification and updates**
   - Razorpay: verify payment and signature; update payment status.
   - Wallet: on success/failure, update payment status accordingly.

8. **Finalize order**
   - When all payment parts are COMPLETED, mark order as paid and trigger WMS sync.
