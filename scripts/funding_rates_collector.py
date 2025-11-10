"""
Continuous Funding Rates Collector - Run 24/7 to collect perpetual funding rates

This script continuously collects funding rates for perpetual futures (every 8 hours).
Funding rates are published at 00:00, 08:00, 16:00 UTC daily.

Usage:
    # Run as continuous service
    python -m scripts.funding_rates_collector

    # Or as Docker service (recommended)
    docker-compose up -d funding-collector
"""

import aiohttp
import asyncio
import asyncpg
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/funding_rates_collector.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class FundingRatesCollector:
    """
    Continuous funding rates collector for perpetual futures.

    Features:
    - Collects funding rates every 8 hours (aligned with Deribit schedule)
    - Supports BTC-PERPETUAL and ETH-PERPETUAL
    - Auto-retry with exponential backoff
    - Graceful shutdown support
    - Stores in funding_rates table
    """

    BASE_URL = "https://www.deribit.com/api/v2/public/get_funding_rate_history"
    RATE_LIMIT_DELAY = 0.05  # 20 req/sec
    MAX_RETRIES = 3

    # Funding rate schedule (UTC times)
    FUNDING_HOURS = [0, 8, 16]  # 00:00, 08:00, 16:00 UTC

    def __init__(self, database_url: str, check_interval_sec: int = 600):
        """
        Initialize funding rates collector.

        Args:
            database_url: PostgreSQL connection URL
            check_interval_sec: How often to check for new funding rates (default: 10 minutes)
        """
        self.database_url = database_url
        self.check_interval_sec = check_interval_sec
        self.pool = None
        self.running = False

        # Instruments to collect (BTC and ETH perpetuals)
        self.instruments = ['BTC-PERPETUAL', 'ETH-PERPETUAL']

        logger.info(
            f"FundingRatesCollector initialized: "
            f"instruments={self.instruments}, check_interval={check_interval_sec}s"
        )

    async def connect(self):
        """Establish database connection pool."""
        try:
            logger.info("Connecting to database...")
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=3,
                command_timeout=60,
                timeout=30
            )
            logger.info("Database connection pool established")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def close(self):
        """Close database connection pool."""
        if self.pool:
            logger.info("Closing database connection pool...")
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def start(self):
        """Start the continuous collector."""
        logger.info("="*80)
        logger.info("FUNDING RATES COLLECTOR STARTED")
        logger.info("="*80)
        logger.info(f"Instruments: {self.instruments}")
        logger.info(f"Funding times: {self.FUNDING_HOURS} UTC")
        logger.info(f"Check interval: {self.check_interval_sec}s")
        logger.info("="*80)

        await self.connect()

        # Do initial backfill to catch any missed rates
        logger.info("Performing initial backfill (last 48 hours)...")
        await self._backfill_recent()

        # Start continuous collection loop
        self.running = True

        try:
            while self.running:
                # Check if we're near a funding time
                now_utc = datetime.now(timezone.utc)
                next_funding_time = self._get_next_funding_time(now_utc)
                time_until_funding = (next_funding_time - now_utc).total_seconds()

                logger.info(
                    f"Current time: {now_utc.strftime('%H:%M')} UTC | "
                    f"Next funding: {next_funding_time.strftime('%H:%M')} UTC | "
                    f"In {time_until_funding/60:.0f} minutes"
                )

                # If funding time was recent (within last check interval), collect it
                if time_until_funding < 0 and abs(time_until_funding) < self.check_interval_sec * 2:
                    logger.info("📊 Funding rate collection triggered!")
                    await self._collect_latest_funding_rates()

                # Wait until next check
                await asyncio.sleep(self.check_interval_sec)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
            self.running = False
        except Exception as e:
            logger.error(f"Fatal error in collector loop: {e}", exc_info=True)
            raise
        finally:
            await self.close()

    async def stop(self):
        """Stop the collector gracefully."""
        logger.info("Stopping funding rates collector...")
        self.running = False

    async def _backfill_recent(self):
        """Backfill funding rates for last 48 hours to catch any missed rates."""
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = end_ts - (48 * 3600)  # 48 hours ago

        for instrument in self.instruments:
            try:
                rates = await self._fetch_funding_rates(instrument, start_ts, end_ts)
                if rates:
                    await self._upsert_funding_rates(instrument, rates)
                    logger.info(f"Backfilled {len(rates)} rates for {instrument}")
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"Error backfilling {instrument}: {e}")

    async def _collect_latest_funding_rates(self):
        """Collect the most recent funding rate for all instruments."""
        # Get last 24 hours to ensure we catch the latest rate
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = end_ts - (24 * 3600)  # 24 hours ago

        total_collected = 0

        for instrument in self.instruments:
            try:
                rates = await self._fetch_funding_rates(instrument, start_ts, end_ts)

                if rates:
                    await self._upsert_funding_rates(instrument, rates)
                    total_collected += len(rates)
                    logger.info(f"✅ Collected {len(rates)} funding rates for {instrument}")
                else:
                    logger.warning(f"No funding rates found for {instrument}")

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"Error collecting funding rate for {instrument}: {e}")

        logger.info(f"📊 Total funding rates collected: {total_collected}")

    async def _fetch_funding_rates(self, instrument: str, start_ts: int, end_ts: int) -> List[Dict]:
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
                    async with session.get(self.BASE_URL, params=params, timeout=10) as resp:
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

    async def _upsert_funding_rates(self, instrument: str, rates: List[Dict]):
        """
        Insert funding rates into database (idempotent).

        Args:
            instrument: Instrument name
            rates: List of funding rate records from API
        """
        if not rates:
            logger.warning(f"{instrument}: No rates to insert")
            return

        async with self.pool.acquire() as conn:
            query = """
            INSERT INTO funding_rates (timestamp, instrument, funding_rate)
            VALUES ($1, $2, $3)
            ON CONFLICT (timestamp, instrument) DO UPDATE SET
                funding_rate = EXCLUDED.funding_rate
            """

            rows = []
            for rate in rates:
                try:
                    timestamp = datetime.fromtimestamp(rate['timestamp'] / 1000, tz=timezone.utc)
                    # Deribit may use 'interest_8h' or 'funding_rate'
                    funding_rate = rate.get('interest_8h', rate.get('funding_rate', 0))

                    rows.append((timestamp, instrument, funding_rate))
                except Exception as e:
                    logger.error(f"Error parsing rate: {rate}, error: {e}")
                    continue

            if rows:
                await conn.executemany(query, rows)
                logger.info(f"{instrument}: Inserted {len(rows)} funding rates")

    def _get_next_funding_time(self, current_time: datetime) -> datetime:
        """
        Calculate next funding time based on Deribit schedule (00:00, 08:00, 16:00 UTC).

        Args:
            current_time: Current datetime (timezone-aware UTC)

        Returns:
            Next funding time (timezone-aware UTC)
        """
        current_hour = current_time.hour

        # Find next funding hour
        next_hour = None
        for funding_hour in self.FUNDING_HOURS:
            if funding_hour > current_hour:
                next_hour = funding_hour
                break

        # If no funding hour found today, use first one tomorrow
        if next_hour is None:
            next_day = current_time + timedelta(days=1)
            return next_day.replace(hour=self.FUNDING_HOURS[0], minute=0, second=0, microsecond=0)

        # Otherwise, use next funding hour today
        return current_time.replace(hour=next_hour, minute=0, second=0, microsecond=0)


async def main():
    """Main entry point."""
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')
    CHECK_INTERVAL = int(os.getenv('FUNDING_CHECK_INTERVAL_SEC', 600))  # 10 minutes

    collector = FundingRatesCollector(
        database_url=DATABASE_URL,
        check_interval_sec=CHECK_INTERVAL
    )

    try:
        await collector.start()
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
        return 0
    except Exception as e:
        logger.error(f"Collector failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    # Run collector
    sys.exit(asyncio.run(main()))
