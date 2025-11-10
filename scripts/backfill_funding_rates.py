"""
Backfill historical funding rates for perpetual futures.

Funding rates are collected every 8 hours (00:00, 08:00, 16:00 UTC).
This script fetches historical funding rates from Deribit API.

Usage:
    python -m scripts.backfill_funding_rates
"""

import aiohttp
import asyncio
import psycopg2
import logging
from datetime import datetime, timezone
from typing import List, Dict
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/funding-rates-backfill.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class FundingRatesBackfiller:
    """Backfill historical funding rates for perpetuals"""

    BASE_URL = "https://www.deribit.com/api/v2/public/get_funding_rate_history"
    RATE_LIMIT_DELAY = 0.05  # 20 req/sec
    MAX_RETRIES = 3

    def __init__(self):
        self.conn = psycopg2.connect("dbname=crypto_data user=postgres")

    async def fetch_funding_rates(
        self,
        instrument: str,
        start_ts: int,
        end_ts: int
    ) -> List[Dict]:
        """
        Fetch funding rate history from Deribit.

        Args:
            instrument: Instrument name (e.g., 'BTC-PERPETUAL')
            start_ts: Start timestamp (seconds)
            end_ts: End timestamp (seconds)

        Returns:
            List of funding rate records
        """
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_ts * 1000,  # API expects milliseconds
            "end_timestamp": end_ts * 1000
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.BASE_URL, params=params) as resp:
                        if resp.status == 429:
                            # Rate limited
                            wait = (2 ** attempt) + 0.5
                            logger.warning(f"Rate limited, waiting {wait}s...")
                            await asyncio.sleep(wait)
                            continue

                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(f"API error {resp.status}: {error_text}")
                            return []

                        data = await resp.json()

                        if 'result' not in data:
                            logger.error(f"Unexpected response: {data}")
                            return []

                        return data['result']

            except Exception as e:
                logger.error(f"Error fetching funding rates (attempt {attempt + 1}): {e}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        return []

    def upsert_funding_rates(self, instrument: str, rates: List[Dict]):
        """
        Insert funding rates into database (idempotent).

        Args:
            instrument: Instrument name
            rates: List of funding rate records from API
        """
        if not rates:
            logger.warning(f"{instrument}: No rates to insert")
            return

        cur = self.conn.cursor()

        query = """
        INSERT INTO funding_rates (timestamp, instrument, funding_rate)
        VALUES (%s, %s, %s)
        ON CONFLICT (timestamp, instrument) DO UPDATE SET
            funding_rate = EXCLUDED.funding_rate
        """

        rows = []
        for rate in rates:
            try:
                timestamp = datetime.fromtimestamp(rate['timestamp'] / 1000, tz=timezone.utc)
                funding_rate = rate.get('interest_8h', rate.get('funding_rate', 0))

                rows.append((timestamp, instrument, funding_rate))
            except Exception as e:
                logger.error(f"Error parsing rate: {rate}, error: {e}")
                continue

        if rows:
            cur.executemany(query, rows)
            self.conn.commit()
            logger.info(f"{instrument}: Inserted {len(rows)} funding rates")

    async def backfill_instrument(
        self,
        instrument: str,
        start_date: str,
        end_date: str
    ) -> int:
        """
        Backfill funding rates for a single instrument.

        Args:
            instrument: Instrument name (e.g., 'BTC-PERPETUAL')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Number of rates backfilled
        """
        logger.info(f"Starting backfill for {instrument} ({start_date} to {end_date})")

        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())

        # Fetch all rates in one API call (Deribit supports large ranges)
        rates = await self.fetch_funding_rates(instrument, start_ts, end_ts)

        # Insert into database
        self.upsert_funding_rates(instrument, rates)

        await asyncio.sleep(self.RATE_LIMIT_DELAY)

        return len(rates)

    def verify_completeness(self, instrument: str, start_date: str, end_date: str):
        """
        Verify funding rates completeness (should be every 8 hours).

        Args:
            instrument: Instrument name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        cur = self.conn.cursor()

        # Count actual rates
        cur.execute("""
            SELECT COUNT(*)
            FROM funding_rates
            WHERE instrument = %s
              AND timestamp >= %s::date
              AND timestamp < %s::date
        """, (instrument, start_date, end_date))

        actual_count = cur.fetchone()[0]

        # Expected: 3 rates per day (00:00, 08:00, 16:00 UTC)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days
        expected_count = days * 3

        coverage_pct = (actual_count / expected_count * 100) if expected_count > 0 else 0

        logger.info(f"{instrument}: {actual_count}/{expected_count} rates ({coverage_pct:.1f}% coverage)")

        # Check for gaps > 8 hours
        cur.execute("""
            SELECT
                timestamp,
                LAG(timestamp) OVER (ORDER BY timestamp) AS prev_timestamp,
                timestamp - LAG(timestamp) OVER (ORDER BY timestamp) AS gap
            FROM funding_rates
            WHERE instrument = %s
              AND timestamp >= %s::date
              AND timestamp < %s::date
        """, (instrument, start_date, end_date))

        gaps = []
        for row in cur.fetchall():
            if row[2] and row[2].total_seconds() > 8 * 3600 + 600:  # > 8h 10min (allow slack)
                gaps.append({
                    'timestamp': row[0],
                    'prev_timestamp': row[1],
                    'gap': row[2]
                })

        if gaps:
            logger.warning(f"{instrument}: Found {len(gaps)} gaps > 8 hours:")
            for gap in gaps[:10]:  # Show first 10
                logger.warning(f"  Gap: {gap['gap']} at {gap['timestamp']}")
        else:
            logger.info(f"{instrument}: ✅ No significant gaps detected")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


async def main():
    """Main execution function"""
    instruments = [
        'BTC-PERPETUAL',
        'ETH-PERPETUAL'
    ]

    # Backfill from inception to today
    start_date = "2016-12-01"  # BTC-PERPETUAL launch
    end_date = datetime.now().strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info("Funding Rates Backfill Started")
    logger.info("=" * 60)
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Instruments: {instruments}")
    logger.info("")

    backfiller = FundingRatesBackfiller()

    try:
        total_rates = 0

        for instrument in instruments:
            count = await backfiller.backfill_instrument(instrument, start_date, end_date)
            total_rates += count
            logger.info("")

            # Verify completeness
            backfiller.verify_completeness(instrument, start_date, end_date)
            logger.info("")

        logger.info("=" * 60)
        logger.info(f"Backfill Complete! Total rates: {total_rates:,}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise

    finally:
        backfiller.close()


if __name__ == '__main__':
    asyncio.run(main())
