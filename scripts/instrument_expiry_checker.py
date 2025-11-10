"""
Instrument Expiry Checker - Parse and check expiry dates from instrument names
"""
from datetime import datetime, timezone
import re
from typing import Optional

def parse_expiry_from_instrument(instrument_name: str) -> Optional[datetime]:
    """
    Parse expiry datetime from Deribit instrument name.

    Format: ETH-10NOV25-3100-C
    - Currency: ETH
    - Expiry: 10NOV25 (10th November 2025, 08:00 UTC)
    - Strike: 3100
    - Type: C (Call) or P (Put)

    Returns:
        Expiry datetime (08:00 UTC on expiry date) or None if parsing fails
    """
    try:
        # Extract date part: 10NOV25
        match = re.match(r'[A-Z]+-(\d{1,2}[A-Z]{3}\d{2})-', instrument_name)
        if not match:
            return None

        date_str = match.group(1)  # e.g., "10NOV25"

        # Parse date
        expiry_date = datetime.strptime(date_str, '%d%b%y')

        # Set time to 08:00 UTC (Deribit expiry time)
        expiry_datetime = expiry_date.replace(hour=8, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        return expiry_datetime

    except Exception as e:
        return None


def is_instrument_expired(instrument_name: str, buffer_minutes: int = 5) -> bool:
    """
    Check if an instrument has expired.

    Args:
        instrument_name: Deribit instrument name (e.g., ETH-10NOV25-3100-C)
        buffer_minutes: Minutes after expiry to consider expired (default 5 min buffer)

    Returns:
        True if instrument has expired, False otherwise
    """
    expiry = parse_expiry_from_instrument(instrument_name)
    if expiry is None:
        # Cannot parse expiry, assume not expired (safer)
        return False

    now = datetime.now(timezone.utc)

    # Add buffer time (e.g., 5 minutes after official expiry)
    from datetime import timedelta
    expiry_with_buffer = expiry + timedelta(minutes=buffer_minutes)

    return now >= expiry_with_buffer


def filter_expired_instruments(instruments: list[str], buffer_minutes: int = 5) -> list[str]:
    """
    Filter out expired instruments from a list.

    Args:
        instruments: List of instrument names
        buffer_minutes: Minutes after expiry to consider expired

    Returns:
        List of non-expired instruments
    """
    return [
        inst for inst in instruments
        if not is_instrument_expired(inst, buffer_minutes)
    ]


def get_next_expiry_time(instruments: list[str]) -> Optional[datetime]:
    """
    Get the next expiry time from a list of instruments.

    Returns:
        Next expiry datetime or None if no valid instruments
    """
    expiry_times = []

    for inst in instruments:
        expiry = parse_expiry_from_instrument(inst)
        if expiry:
            expiry_times.append(expiry)

    if not expiry_times:
        return None

    return min(expiry_times)


# Example usage
if __name__ == "__main__":
    # Test parsing
    test_instruments = [
        "ETH-10NOV25-3100-C",
        "ETH-29NOV24-3600-P",
        "BTC-27DEC24-100000-C"
    ]

    print("Testing expiry parsing:")
    print("=" * 60)
    for inst in test_instruments:
        expiry = parse_expiry_from_instrument(inst)
        is_exp = is_instrument_expired(inst)
        print(f"{inst}")
        print(f"  Expiry: {expiry}")
        print(f"  Expired: {is_exp}")
        print()

    # Test filtering
    print("Filtering expired instruments:")
    print("=" * 60)
    active = filter_expired_instruments(test_instruments)
    print(f"Active instruments: {active}")

    # Next expiry
    next_exp = get_next_expiry_time(test_instruments)
    print(f"\nNext expiry: {next_exp}")
