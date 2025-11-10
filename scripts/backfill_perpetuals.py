"""
Perpetuals OHLCV Backfill Script
Task: T-005
Acceptance Criteria: AC-004, AC-005, AC-006

Backfills perpetual futures OHLCV data from Deribit API (2016-2025).
Supports BTC-PERPETUAL and ETH-PERPETUAL.

Usage:
    python -m scripts.backfill_perpetuals \
        --instruments BTC-PERPETUAL,ETH-PERPETUAL \
        --start 2016-12-01 \
        --end 2025-10-18 \
        --resolution 1
"""

import aiohttp
import asyncio
import psycopg2
import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for logging_config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from logging_config import setup_logging


class PerpetualBackfiller:
    """Handles backfilling perpetual futures OHLCV data from Deribit"""

    BASE_URL = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
    MAX_CANDLES_PER_CALL = 5000
    RATE_LIMIT_DELAY = 0.05  # 20 req/sec = 0.05s delay
    MAX_RETRIES = 3

    def __init__(self, db_connection_string="dbname=crypto_data user=postgres"):
        self.db_conn_str = db_connection_string
        self.logger = setup_logging()
        self.total_inserted = 0

    async def fetch_ohlcv_chunk(self, session, instrument, start_ts, end_ts,
                                resolution=1, retry_count=0):
        """
        Fetch OHLCV data chunk from Deribit API

        Args:
            session: aiohttp ClientSession
            instrument: Instrument name (e.g., BTC-PERPETUAL)
            start_ts: Start timestamp in milliseconds
            end_ts: End timestamp in milliseconds
            resolution: Resolution in minutes (default: 1)
            retry_count: Current retry attempt

        Returns:
            dict: API response with OHLCV data
        """
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "resolution": resolution
        }

        try:
            async with session.get(self.BASE_URL, params=params) as response:
                if response.status == 429:
                    # Rate limit hit - exponential backoff
                    if retry_count < self.MAX_RETRIES:
                        wait_time = 2 ** retry_count
                        self.logger.warning(
                            f"Rate limit hit (429). Retrying in {wait_time}s... "
                            f"(Attempt {retry_count + 1}/{self.MAX_RETRIES})"
                        )
                        await asyncio.sleep(wait_time)
                        return await self.fetch_ohlcv_chunk(
                            session, instrument, start_ts, end_ts,
                            resolution, retry_count + 1
                        )
                    else:
                        self.logger.error(
                            f"Max retries ({self.MAX_RETRIES}) exceeded for "
                            f"{instrument} at {start_ts}"
                        )
                        return None

                if response.status != 200:
                    self.logger.error(
                        f"API error {response.status} for {instrument}: "
                        f"{await response.text()}"
                    )
                    return None

                data = await response.json()

                # Check for API error in response
                if 'error' in data:
                    self.logger.error(
                        f"API returned error for {instrument}: {data['error']}"
                    )
                    return None

                return data.get('result', {})

        except Exception as e:
            self.logger.error(
                f"Exception fetching {instrument} at {start_ts}: {e}"
            )
            if retry_count < self.MAX_RETRIES:
                await asyncio.sleep(2 ** retry_count)
                return await self.fetch_ohlcv_chunk(
                    session, instrument, start_ts, end_ts,
                    resolution, retry_count + 1
                )
            return None

    def upsert_to_db(self, rows):
        """
        Upsert OHLCV rows to database (idempotent)

        Args:
            rows: List of tuples (timestamp, instrument, open, high, low, close, volume)
        """
        if not rows:
            return

        conn = psycopg2.connect(self.db_conn_str)
        try:
            cursor = conn.cursor()
            query = """
                INSERT INTO perpetuals_ohlcv
                    (timestamp, instrument, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, instrument)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """
            cursor.executemany(query, rows)
            conn.commit()
            self.total_inserted += len(rows)

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error upserting {len(rows)} rows: {e}")
            raise
        finally:
            conn.close()

    async def backfill_instrument(self, instrument, start_date, end_date, resolution=1):
        """
        Backfill single instrument from start_date to end_date

        Args:
            instrument: Instrument name (e.g., BTC-PERPETUAL)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            resolution: Resolution in minutes (default: 1)
        """
        self.logger.info(f"Starting backfill for {instrument} from {start_date} to {end_date}")

        # Convert dates to millisecond timestamps
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        # Calculate expected candles for progress tracking
        expected_candles = (end_ts - start_ts) // (resolution * 60 * 1000)
        self.logger.info(f"Expected ~{expected_candles:,} candles for {instrument}")

        current_ts = start_ts
        candles_inserted = 0
        last_progress_log = 0

        async with aiohttp.ClientSession() as session:
            while current_ts < end_ts:
                # Calculate chunk end (max 5000 candles per call)
                chunk_size_ms = self.MAX_CANDLES_PER_CALL * resolution * 60 * 1000
                chunk_end_ts = min(current_ts + chunk_size_ms, end_ts)

                # Fetch data chunk
                result = await self.fetch_ohlcv_chunk(
                    session, instrument, current_ts, chunk_end_ts, resolution
                )

                if result is None:
                    self.logger.error(
                        f"Skipping chunk {current_ts} - {chunk_end_ts} due to error"
                    )
                    current_ts = chunk_end_ts
                    continue

                # Extract OHLCV data
                ticks = result.get('ticks', [])
                opens = result.get('open', [])
                highs = result.get('high', [])
                lows = result.get('low', [])
                closes = result.get('close', [])
                volumes = result.get('volume', [])

                # Prepare rows for database insert
                rows = []
                for i in range(len(ticks)):
                    timestamp = datetime.fromtimestamp(ticks[i] / 1000)
                    rows.append((
                        timestamp,
                        instrument,
                        float(opens[i]),
                        float(highs[i]),
                        float(lows[i]),
                        float(closes[i]),
                        float(volumes[i])
                    ))

                # Upsert to database
                if rows:
                    self.upsert_to_db(rows)
                    candles_inserted += len(rows)

                    # Log progress every 10k candles
                    if candles_inserted - last_progress_log >= 10000:
                        progress_pct = (candles_inserted / expected_candles) * 100
                        self.logger.info(
                            f"Progress: {candles_inserted:,}/{expected_candles:,} candles "
                            f"({progress_pct:.1f}%) - {instrument}"
                        )
                        last_progress_log = candles_inserted

                # Move to next chunk
                current_ts = chunk_end_ts

                # Rate limiting
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        self.logger.info(
            f"✓ Completed backfill for {instrument}: "
            f"{candles_inserted:,} candles inserted"
        )
        return candles_inserted

    async def backfill_multiple(self, instruments, start_date, end_date, resolution=1):
        """
        Backfill multiple instruments

        Args:
            instruments: List of instrument names
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            resolution: Resolution in minutes (default: 1)
        """
        start_time = datetime.now()
        self.logger.info(
            f"Starting backfill for {len(instruments)} instruments: "
            f"{', '.join(instruments)}"
        )

        total_candles = 0
        for instrument in instruments:
            candles = await self.backfill_instrument(
                instrument, start_date, end_date, resolution
            )
            total_candles += candles

        elapsed = (datetime.now() - start_time).total_seconds()
        self.logger.info(
            f"✓ Backfill complete: {total_candles:,} candles in {elapsed:.1f}s "
            f"({total_candles/elapsed:.1f} candles/sec)"
        )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Backfill perpetuals OHLCV data from Deribit"
    )
    parser.add_argument(
        "--instruments",
        type=str,
        required=True,
        help="Comma-separated instrument names (e.g., BTC-PERPETUAL,ETH-PERPETUAL)"
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=1,
        help="Resolution in minutes (default: 1)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="dbname=crypto_data user=postgres",
        help="PostgreSQL connection string"
    )

    args = parser.parse_args()

    # Parse instruments
    instruments = [i.strip() for i in args.instruments.split(',')]

    # Create backfiller and run
    backfiller = PerpetualBackfiller(args.db)

    try:
        asyncio.run(
            backfiller.backfill_multiple(
                instruments, args.start, args.end, args.resolution
            )
        )
        return 0
    except Exception as e:
        backfiller.logger.error(f"Backfill failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
