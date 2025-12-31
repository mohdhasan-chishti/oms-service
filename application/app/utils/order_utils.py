from app.core.constants import OrderStatus
from app.validations.stock import StockValidator
from app.services.typesense_service import TypesenseService
from app.config.settings import OMSConfigs

from datetime import UTC, datetime, timedelta, time
from zoneinfo import ZoneInfo
from app.models.common import get_ist_now

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("app.utils.order_utils")

configs = OMSConfigs()
cap_qty = configs.CAP_QUANTITY
safety_qty = configs.SAFETY_QUANTITY
update_typesense = configs.UPDATE_TYPESENSE_ENABLED
target_collection = configs.TYPESENSE_COLLECTION_NAME

# Parse store time strings (format: HH:MM)
store_open_parts = configs.STORE_OPEN_TIME.split(':')
store_open_hour = int(store_open_parts[0])
store_open_minute = int(store_open_parts[1])

store_close_parts = configs.STORE_CLOSE_TIME.split(':')
store_close_hour = int(store_close_parts[0])
store_close_minute = int(store_close_parts[1])

store_open = time(store_open_hour, store_open_minute)
store_close = time(store_close_hour, store_close_minute)

eta_diff_minutes = configs.ETA_DIFF_MINUTES
eta_adjust_minutes = configs.ETA_ADJUST_MINUTES
IST = ZoneInfo("Asia/Kolkata")

def get_ist(datetime_str: str):
    if datetime_str:
        dt_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    else:
        dt_time = get_ist_now().replace(tzinfo=None)
    return dt_time

def get_utc(datetime_str: str):
    current_utc = datetime.now(UTC)
    if datetime_str:
        # Parse the datetime string
        dt_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))

        # If the datetime is timezone-naive, assume it's IST (from app origin)
        if dt_time.tzinfo is None:
            # Treat naive datetime as IST and convert to UTC
            dt_time = dt_time.replace(tzinfo=IST).astimezone(UTC)
        else:
            # Convert to UTC if it's already timezone-aware
            dt_time = dt_time.astimezone(UTC)

        current_time = current_utc.time()

        # Check if we're in the overnight closed period (after close OR before open)
        # Store closed: 12:30 PM to 2:30 AM next day
        is_closed_hours = current_time >= store_close or current_time < store_open

        if is_closed_hours:
            # Calculate next store opening time
            if current_time >= store_close:
                # After close today, open tomorrow
                next_open = current_utc.replace(hour=store_open_hour, minute=store_open_minute, second=0, microsecond=0) + timedelta(days=1)
            else:
                # Before open today, open is today
                next_open = current_utc.replace(hour=store_open_hour, minute=store_open_minute, second=0, microsecond=0)

            # Add adjustment time to the opening time
            dt_time = max(next_open + timedelta(minutes=eta_adjust_minutes), dt_time)
        elif dt_time < current_utc + timedelta(minutes=eta_diff_minutes):
            # Store is open but order time is too soon
            dt_time = current_utc + timedelta(minutes=eta_adjust_minutes)
    else:
        dt_time = current_utc
    return dt_time

def can_cancel_order(current_status: int, marketplace: str = None) -> bool:
    if current_status in [OrderStatus.CANCELED, OrderStatus.CANCELLED_PENDING_REFUND]:
        return False

    if marketplace and marketplace.lower() == 'ondc':
        if current_status > 27:
            logger.info(f"ONDC order cannot be cancelled | status={current_status}")
            return False
        return True

    can_cancel = [
        OrderStatus.POTIONS_SYNCED,  # 18
        OrderStatus.POTIONS_SYNC_FAILED, # 19
        OrderStatus.WMS_SYNCED,      # 21
        OrderStatus.WMS_SYNC_FAILED, # 22
        OrderStatus.WMS_OPEN,        # 23
        OrderStatus.WMS_INPROGRESS   # 24
    ]

    return current_status in can_cancel

async def block_quantity_in_redis(enriched_items, facility_name):
    logger.info(f"Starting block_quantity_in_redis for facility: {facility_name}, items count: {len(enriched_items)}")
    bulk_update_data = []
    for item in enriched_items:
        logger.info(f"Processing item: wh_sku={item.get('wh_sku')}, quantity={item.get('quantity')}, pack_uom_quantity={item.get('pack_uom_quantity')}")
        stock_validator = StockValidator(facility_name, item["wh_sku"])
        ims_new_available_stock = stock_validator.block_stock(item["quantity"] * item["pack_uom_quantity"])
        logger.info(f"After blocking stock for wh_sku={item['wh_sku']}: ims_new_available_stock={ims_new_available_stock}")
        
        if not update_typesense:
            logger.error(f"Typesense update disabled, skipping for wh_sku={item['wh_sku']}")
            continue
        
        typesense_qty = item.get("available_qty")
        logger.info(f"Typesense current qty for wh_sku={item['wh_sku']}: {typesense_qty}")

        # Get resolved safety stock from stock validator (category-level)
        resolved_safety_qty = stock_validator.safety_stock_manager.get_safety_stock({"category": item.get("category"), "sub_category": item.get("sub_category"), "sub_sub_category": item.get("sub_sub_category")})
        logger.info(f"Resolved safety stock for wh_sku={item['wh_sku']}: {resolved_safety_qty} (env_default={safety_qty})")

        # Calculate Typesense quantity
        pack_uom_qty = item.get("pack_uom_quantity", 1)
        if ims_new_available_stock > resolved_safety_qty:
            adjusted_qty = ims_new_available_stock - resolved_safety_qty
            calculated_qty = int(adjusted_qty // pack_uom_qty)
            new_typesense_qty = min(calculated_qty, cap_qty)
            new_availability = True
        else:
            new_typesense_qty = 0
            new_availability = False

        logger.info(f"Calculated new values for wh_sku={item['wh_sku']}: new_typesense_qty={new_typesense_qty}, new_availability={new_availability}, pack_uom={pack_uom_qty}")
        
        if typesense_qty != new_typesense_qty:
            update_item = {
                'id': item.get("document_id"),
                'is_available': new_availability,
                'available_qty': new_typesense_qty,
                'wh_sku': item.get("wh_sku"),
                'pack_uom_quantity': pack_uom_qty, 
                'unit_price': item.get("unit_price")
            }
            bulk_update_data.append(update_item)
            logger.info(f"Added to bulk update for wh_sku={item['wh_sku']}, pack_uom_qty={pack_uom_qty}: {update_item}")
        else:
            logger.info(f"No change needed for wh_sku={item['wh_sku']}, pack_uom_qty={pack_uom_qty}, current={typesense_qty}, new={new_typesense_qty}")
    
    logger.info(f"block_quantity_in_redis completed, bulk_update_data count: {len(bulk_update_data)}")
    return bulk_update_data

async def block_quantity_in_typesense(bulk_update_data, facility_name):
    # these can be multiple docs for one wh_sku so we need to update all of them
    # we have to prepare the search for all wh_sku from bulk_update_data and get the docs
    typesense = TypesenseService()
    wh_skus = [item["wh_sku"] for item in bulk_update_data]
    logger.info(f"Fetching Typesense documents for wh_skus: {wh_skus}")

    try:
        typesense_docs = await typesense.get_document_by_wh_skus(wh_skus, collection=target_collection, facility_name=facility_name)
        logger.info(f"Retrieved {len(typesense_docs)} documents from Typesense for facility: {facility_name}")
    except Exception as e:
        logger.error(f"Failed to fetch documents from Typesense: {str(e)}")
        raise

    # now we got the typesense_docs now map the typesense_docs to bulk_update_data on wh_sku and pack_uom_quantity and populate the same is_available field and available_qty field
    bulk_update_data_by_sku_pack = {}
    for item in bulk_update_data:
        sku_pack_id = (item["wh_sku"], int(item.get("pack_uom_quantity", 1)))
        bulk_update_data_by_sku_pack[sku_pack_id] = {
            "is_available": item["is_available"],
            "available_qty": item["available_qty"]
        }

    # Match documents and update using bulk_update_data
    updated_docs = []
    for doc in typesense_docs:
        sku_pack_id = (doc["wh_sku"], int(doc.get("pack_uom_qty", 1)))
        if sku_pack_id in bulk_update_data_by_sku_pack:
            item = bulk_update_data_by_sku_pack[sku_pack_id]
            prepare_for_update = {
                "id": doc["id"],
                "is_available": item["is_available"],
                "available_qty": item["available_qty"]
            }
            updated_docs.append(prepare_for_update)
            logger.info(f"Prepared update for document id={doc['id']}, wh_sku={doc['wh_sku']}, pack_uom_qty={sku_pack_id[1]}: available_qty={item['available_qty']}")
        else:
            logger.warning(f"Document wh_sku={doc['wh_sku']}, pack_uom_qty={sku_pack_id[1]} not found in bulk_update_data")
    logger.info(f"Prepared {len(updated_docs)} documents for bulk update in Typesense")

    if updated_docs:
        try:
            await typesense.bulk_update_documents(updated_docs, collection=target_collection)
            logger.info(f"Successfully updated {len(updated_docs)} documents in Typesense collection: {target_collection}")
        except Exception as e:
            logger.error(f"Failed to bulk update documents in Typesense: {str(e)}")
            raise
    else:
        logger.warning("No documents to update in Typesense")