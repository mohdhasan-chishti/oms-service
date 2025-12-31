# Order Status Documentation

This document provides a comprehensive overview of all order statuses used in the Rozana OMS (Order Management System). Order statuses track the lifecycle of an order from creation to completion across multiple systems: OMS, WMS (Warehouse Management System), and TMS (Transport Management System).

## Status Categories

Order statuses are organized into three main categories:

1. **OMS Statuses (0-20)**: Internal order management statuses
2. **WMS Statuses (21-30)**: Warehouse and fulfillment statuses  
3. **TMS Statuses (31-40)**: Transport and delivery statuses

## Complete Status List

### OMS (Order Management System) Statuses

| Status Code | Status Name | Customer Display | Description | Cancellable |
|-------------|-------------|------------------|-------------|-------------|
| 0 | DRAFT | Payment Pending | Order created but payment not completed | ✅ Yes |
| 10 | OPEN | Processing | Order confirmed and payment completed | ✅ Yes |
| 11 | FULFILLED | Delivered | Order successfully completed and delivered | ❌ No |
| 12 | PARTIALLY_FULFILLED | Delivered | Order partially delivered (some items) | ❌ No |
| 13 | UNFULFILLED | Delivery Failed | Order could not be fulfilled | ❌ No |
| 14 | CANCELED | Cancelled | Order cancelled by customer or system | ❌ No |
| 15 | RETURN | Return Initiated | Return process started for order | ❌ No |
| 16 | CANCELLED_PENDING_REFUND | Cancelled | Order cancelled, refund in progress | ❌ No |
| 17 | RETURNED | Returned | Order successfully returned | ❌ No |

### WMS (Warehouse Management System) Statuses

| Status Code | Status Name | Customer Display | Description | Cancellable |
|-------------|-------------|------------------|-------------|-------------|
| 21 | WMS_SYNCED | Confirmed | Order successfully sent to warehouse | ✅ Yes |
| 22 | WMS_SYNC_FAILED | Processing | Failed to sync order with warehouse | ✅ Yes |
| 23 | WMS_OPEN | Confirmed | Order received and queued in warehouse | ✅ Yes |
| 24 | WMS_INPROGRESS | Packing Your Order | Order being processed in warehouse | ✅ Yes |
| 25 | WMS_PICKED | Packing Your Order | Items picked from inventory | ❌ No |
| 26 | WMS_FULFILLED | Packed | Order packed and ready for dispatch | ❌ No |
| 27 | WMS_INVOICED | Ready For Dispatch | Order invoiced and ready for shipping | ❌ No |
| 28 | WMS_CANCELED | Cancelled | Order cancelled at warehouse level | ❌ No |

### TMS (Transport Management System) Statuses

| Status Code | Status Name | Customer Display | Description | Cancellable |
|-------------|-------------|------------------|-------------|-------------|
| 31 | TMS_SYNCED | Finding Rider | Order sent to transport system | ❌ No |
| 32 | TMS_SYNC_FAILED | Finding Rider | Failed to sync with transport system | ❌ No |
| 33 | RIDER_ASSIGNED | Rider Assigned | Delivery agent assigned to order | ❌ No |
| 34 | TMS_OUT_FOR_DELIVERY | Out For Delivery | Order is out for delivery | ❌ No |
| 35 | TMS_DELIVERED | Delivered | Order successfully delivered | ❌ No |
| 36 | TMS_RETURN_INITIATED | Return Initiated | Return delivery started | ❌ No |
| 37 | TMS_RETURNED | Returned | Order returned via transport | ❌ No |

## Order Status Flow

The typical order progression follows this flow:

```
DRAFT (0) 
    ↓ (Payment Completed)
OPEN (10)
    ↓ (Sent to Warehouse)
WMS_SYNCED (21) / WMS_SYNC_FAILED (22)
    ↓ (Warehouse Processing)
WMS_OPEN (23)
    ↓ (Processing Started)
WMS_INPROGRESS (24)
    ↓ (Items Picked)
WMS_PICKED (25)
    ↓ (Order Packed)
WMS_FULFILLED (26)
    ↓ (Invoice Generated)
WMS_INVOICED (27)
    ↓ (Sent to Transport)
TMS_SYNCED (31) / TMS_SYNC_FAILED (32)
    ↓ (Rider Assignment)
RIDER_ASSIGNED (33)
    ↓ (Out for Delivery)
TMS_OUT_FOR_DELIVERY (34)
    ↓ (Delivery Complete)
TMS_DELIVERED (35) / FULFILLED (11)
```

## Cancellation Rules

Orders can be cancelled at specific statuses only:

### Cancellable Statuses
- **DRAFT (0)**: Before payment completion
- **OPEN (10)**: After payment, before warehouse processing
- **WMS_SYNCED (21)**: After warehouse sync, before processing starts
- **WMS_SYNC_FAILED (22)**: When warehouse sync fails
- **WMS_OPEN (23)**: When queued in warehouse
- **WMS_INPROGRESS (24)**: During warehouse processing (early stages)

### Non-Cancellable Statuses
- **WMS_PICKED (25)** and beyond: Items already picked/packed
- **TMS statuses (31+)**: Order in transport system
- **Final statuses**: FULFILLED, CANCELED, RETURNED, etc.

## Customer-Facing Status Mapping

The system shows simplified, customer-friendly status names instead of internal technical statuses:

| Internal Status Group | Customer Display |
|----------------------|------------------|
| DRAFT | Payment Pending |
| OPEN, WMS_SYNC_FAILED | Processing |
| WMS_SYNCED, WMS_OPEN | Confirmed |
| WMS_INPROGRESS, WMS_PICKED | Packing Your Order |
| WMS_FULFILLED | Packed |
| WMS_INVOICED | Ready For Dispatch |
| TMS_SYNCED, TMS_SYNC_FAILED | Finding Rider |
| RIDER_ASSIGNED | Rider Assigned |
| TMS_OUT_FOR_DELIVERY | Out For Delivery |
| FULFILLED, PARTIALLY_FULFILLED, TMS_DELIVERED | Delivered |
| CANCELED, CANCELLED_PENDING_REFUND, WMS_CANCELED | Cancelled |
| UNFULFILLED | Delivery Failed |
| RETURN, TMS_RETURN_INITIATED | Return Initiated |
| RETURNED, TMS_RETURNED | Returned |

## Status Validation Methods

The system provides several utility methods for status validation:

### Check Status Category
- `OrderStatus.is_rozana_status(status_code)`: Checks if status is OMS-managed
- `OrderStatus.is_wms_status(status_code)`: Checks if status is WMS-managed  
- `OrderStatus.is_tms_status(status_code)`: Checks if status is TMS-managed

### Check Cancellation Eligibility
- `can_cancel_order(current_status)`: Returns true if order can be cancelled

### Get Customer Display Name
- `OrderStatus.get_customer_status_name(status_code)`: Returns customer-friendly status name

## Database Status Mapping

The system maintains a mapping between database string representations and integer status codes:

| Database String | Status Code | Status Name |
|----------------|-------------|-------------|
| oms_draft | 0 | DRAFT |
| oms_open | 10 | OPEN |
| oms_fulfilled | 11 | FULFILLED |
| oms_partial_fulfilled | 12 | PARTIALLY_FULFILLED |
| oms_unfulfilled | 13 | UNFULFILLED |
| oms_canceled | 14 | CANCELED |
| oms_return_initiated | 15 | RETURN |
| oms_returned | 17 | RETURNED |
| wms_synced | 21 | WMS_SYNCED |
| wms_sync_failed | 22 | WMS_SYNC_FAILED |
| open | 23 | WMS_OPEN |
| in_progress | 24 | WMS_INPROGRESS |
| picked | 25 | WMS_PICKED |
| fulfilled | 26 | WMS_FULFILLED |
| invoiced | 27 | WMS_INVOICED |
| tms_synced | 31 | TMS_SYNCED |
| tms_sync_failed | 32 | TMS_SYNC_FAILED |
| rider_assigned | 33 | RIDER_ASSIGNED |
| out_for_delivery | 34 | TMS_OUT_FOR_DELIVERY |
| delivered | 35 | TMS_DELIVERED |

## Related Status Systems

### Payment Status (50-59)
- **PENDING (50)**: Payment not completed
- **COMPLETED (51)**: Payment successful
- **FAILED (52)**: Payment failed
- **REFUNDED (53)**: Payment refunded

### Refund Status (60-69)  
- **CREATED (60)**: Refund request created
- **PENDING (61)**: Refund in progress
- **PROCESSED (62)**: Refund completed
- **FAILED (63)**: Refund failed

## Implementation Notes

1. **Status Codes**: Use integer constants for performance and consistency
2. **Customer Display**: Always use `get_customer_status_name()` for user-facing displays
3. **Validation**: Use provided validation methods before status transitions
4. **Cancellation**: Check `can_cancel_order()` before allowing cancellation
5. **Database**: Use `DB_STATUS_MAP` for string-to-integer conversions

## Version History

- **v1.0**: Initial status system with basic OMS statuses
- **v1.1**: Added WMS integration statuses (21-28)
- **v1.2**: Added TMS integration statuses (31-37)
- **v1.3**: Added CANCELLED_PENDING_REFUND status (16)
- **v1.4**: Enhanced customer status mapping and validation methods
