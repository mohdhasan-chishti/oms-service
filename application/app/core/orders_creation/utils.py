"""
Utility functions for order creation
"""
import uuid
from collections import defaultdict
from typing import Dict, List


def group_items_by_facility(items: List, default_facility: str) -> Dict[str, List]:
    """
    Group items by facility.
    Returns: Dict mapping facility_name to list of items
    """
    facility_groups = defaultdict(list)
    for item in items:
        facility_name = item.facility_name or default_facility
        facility_groups[facility_name].append(item)
    return dict(facility_groups)


def generate_parent_order_id() -> str:
    """Generate a unique parent order ID for the order."""
    return str(uuid.uuid4())
