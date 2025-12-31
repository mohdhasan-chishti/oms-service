"""
Utility functions for date and time formatting.
"""

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")


def get_ist_now() -> datetime:
    """
    Get current datetime in IST timezone.
    Returns:
        Current datetime object with IST timezone
    """
    return datetime.now(IST)


def format_datetime_readable(dt: Optional[datetime]) -> Optional[str]:
    """
    Format datetime object to human readable format.
    
    Args:
        dt: datetime object to format
        
    Returns:
        Formatted string like "January 15, 2024 at 2:30 PM" or None if dt is None
    """
    if dt is None:
        return None
    
    # Keep the datetime in its original timezone (don't convert to system timezone)
    # This preserves IST timezone when IST datetime is passed
    return dt.strftime("%B %d, %Y at %I:%M %p")


def format_timestamp_readable(timestamp: Optional[int]) -> Optional[str]:
    """
    Convert Unix timestamp to human readable format.
    
    Args:
        timestamp: Unix timestamp (seconds since epoch)
        
    Returns:
        Formatted string like "January 15, 2024 at 2:30 PM" or None if timestamp is None
    """
    if timestamp is None:
        return None
    # Convert UTC timestamp to local timezone
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone()
    return format_datetime_readable(dt)


def format_datetime_ist(dt: Optional[datetime]) -> Optional[str]:
    """
    Convert UTC datetime to IST and format to ISO string.
    Handles both datetime objects and string inputs gracefully.

    Returns:
        ISO formatted string in IST timezone or None if dt is None
    """
    if dt is None:
        return None
    
    # Handle string inputs (from legacy orders)
    if isinstance(dt, str):
        if not dt.strip():
            return None
        try:
            # Try to parse the string as datetime
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            try:
                # Try common datetime formats
                dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
            except (ValueError, AttributeError):
                # If all parsing fails, return None
                return None
    
    # Handle datetime objects
    if not isinstance(dt, datetime):
        return None
        
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST)
    return ist_dt.isoformat() if ist_dt else None
