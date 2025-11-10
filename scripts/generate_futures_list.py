"""
Generate list of historical futures instruments for backfill.

Deribit futures expire on the last Friday of each month.
This script generates a complete list of historical futures from 2019 to present.

Usage:
    python -m scripts.generate_futures_list
"""

import json
from datetime import datetime, timedelta
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/generate-futures-list.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def get_last_friday_of_month(year: int, month: int) -> datetime:
    """
    Get the last Friday of a given month.

    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)

    Returns:
        datetime object for last Friday of the month
    """
    # Start with last day of month
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)

    # Find last Friday (4 = Friday in weekday())
    while last_day.weekday() != 4:
        last_day -= timedelta(days=1)

    return last_day


def generate_futures_instruments(
    start_date: str,
    end_date: str,
    currencies: list = ["BTC", "ETH"]
) -> list:
    """
    Generate list of futures instruments based on expiry schedule.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        currencies: List of currencies (default: BTC, ETH)

    Returns:
        List of futures instrument names with metadata
    """
    futures = []

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    logger.info(f"Generating futures list from {start_date} to {end_date}")
    logger.info(f"Currencies: {currencies}")

    current_year = start.year
    current_month = start.month

    while True:
        expiry_date = get_last_friday_of_month(current_year, current_month)

        # Stop if expiry is beyond end date
        if expiry_date > end:
            break

        # Only include if expiry is after start date
        if expiry_date >= start:
            for currency in currencies:
                # Format: BTC-27DEC24, ETH-29NOV24
                instrument_name = f"{currency}-{expiry_date.strftime('%d%b%y').upper()}"

                # Estimate when this contract started trading
                # Usually ~1 month before expiry, but can be earlier
                # Conservative: 2 months before expiry
                trading_start = expiry_date - timedelta(days=60)

                futures.append({
                    "instrument": instrument_name,
                    "currency": currency,
                    "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                    "estimated_start": trading_start.strftime("%Y-%m-%d"),
                    "year": current_year,
                    "month": current_month
                })

        # Next month
        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1

    logger.info(f"Generated {len(futures)} futures instruments")
    logger.info(f"  BTC: {len([f for f in futures if f['currency'] == 'BTC'])}")
    logger.info(f"  ETH: {len([f for f in futures if f['currency'] == 'ETH'])}")

    return futures


def save_futures_list(futures: list, output_path: str = "data/historical_futures_list.json"):
    """
    Save futures list to JSON file.

    Args:
        futures: List of futures instruments
        output_path: Output file path
    """
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(futures, f, indent=2)

    logger.info(f"Saved {len(futures)} instruments to {output_path}")


def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("Historical Futures List Generation")
    logger.info("=" * 60)

    # BTC futures started: June 2019
    # ETH futures started: January 2020
    # Generate up to current month + 3 months (active + near-term)

    btc_start = "2019-06-01"
    eth_start = "2020-01-01"

    # End date: 3 months from now
    end_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    logger.info("\n=== BTC Futures ===")
    btc_futures = generate_futures_instruments(btc_start, end_date, ["BTC"])

    logger.info("\n=== ETH Futures ===")
    eth_futures = generate_futures_instruments(eth_start, end_date, ["ETH"])

    # Combine
    all_futures = btc_futures + eth_futures

    # Sort by expiry date
    all_futures.sort(key=lambda x: x['expiry_date'])

    logger.info("\n=== Summary ===")
    logger.info(f"Total futures: {len(all_futures)}")
    logger.info(f"  BTC: {len(btc_futures)} (from {btc_start})")
    logger.info(f"  ETH: {len(eth_futures)} (from {eth_start})")
    logger.info(f"Date range: {all_futures[0]['expiry_date']} to {all_futures[-1]['expiry_date']}")

    # Save to file
    save_futures_list(all_futures)

    # Show sample
    logger.info("\n=== Sample Instruments (first 10) ===")
    for future in all_futures[:10]:
        logger.info(f"  {future['instrument']:20} Expiry: {future['expiry_date']}  "
                   f"Start: {future['estimated_start']}")

    logger.info("\n=== Sample Instruments (last 10) ===")
    for future in all_futures[-10:]:
        logger.info(f"  {future['instrument']:20} Expiry: {future['expiry_date']}  "
                   f"Start: {future['estimated_start']}")

    logger.info("\n" + "=" * 60)
    logger.info("Generation Complete!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
