"""
Backfill historical futures OHLCV data from Deribit.

This script fetches historical 1-minute OHLCV data for all dated futures
contracts (expired + active) from Deribit's public API.

Usage:
    # Backfill all instruments
    python -m scripts.backfill_futures --all

    # Backfill specific instruments
    python -m scripts.backfill_futures --instruments BTC-27DEC24,ETH-29NOV24

    # Backfill specific currency
    python -m scripts.backfill_futures --currency BTC
"""

import aiohttp
import asyncio
import psycopg2
import logging
import argparse
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/futures-backfill.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class FuturesBackfiller:
    """Backfill historical futures OHLCV from Deribit"""

    BASE_URL = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
    MAX_CANDLES_PER_CALL = 5000
    RATE_LIMIT_DELAY = 0.05  # 20 req/sec
    MAX_RETRIES = 3

    def __init__(self):
        self.conn = psycopg2.connect("dbname=crypto_data user=postgres")
        self.total_candles = 0
        self.total_api_calls = 0
        self.failed_instruments = []

    async def fetch_ohlcv_chunk(
        self,
        session: aiohttp.ClientSession,
        instrument: str,
        start_ts: int,
        end_ts: int
    ) -> List[Dict]:
        """
        Fetch single OHLCV chunk from Deribit (up to 5000 candles).

        Args:
            session: aiohttp client session
            instrument: Instrument name (e.g., 'BTC-27DEC24')
            start_ts: Start timestamp (seconds)
            end_ts: End timestamp (seconds)

        Returns:
            List of candle dictionaries
        """
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_ts * 1000,  # API expects milliseconds
            "end_timestamp": end_ts * 1000,
            "resolution": 1  # 1 minute
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    self.total_api_calls += 1

                    if resp.status == 404:
                        # Instrument doesn't exist or has no data
                        logger.debug(f"{instrument}: No data (404)")
                        return []

                    if resp.status == 429:
                        # Rate limited
                        wait = (2 ** attempt) + 0.5
                        logger.warning(f"{instrument}: Rate limited, waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"{instrument}: API error {resp.status}: {error_text}")
                        return []

                    data = await resp.json()

                    if 'result' not in data:
                        logger.error(f"{instrument}: Unexpected response: {data}")
                        return []

                    if data['result']['status'] != 'ok':
                        logger.warning(f"{instrument}: API returned status '{data['result']['status']}'")
                        return []

                    result = data['result']

                    # Parse candles
                    candles = []
                    if 'ticks' in result and len(result['ticks']) > 0:
                        for i in range(len(result['ticks'])):
                            try:
                                candles.append({
                                    'timestamp': datetime.fromtimestamp(
                                        result['ticks'][i] / 1000,
                                        tz=timezone.utc
                                    ),
                                    'open': float(result['open'][i]),
                                    'high': float(result['high'][i]),
                                    'low': float(result['low'][i]),
                                    'close': float(result['close'][i]),
                                    'volume': float(result['volume'][i])
                                })
                            except (KeyError, IndexError, ValueError) as e:
                                logger.error(f"{instrument}: Error parsing candle {i}: {e}")
                                continue

                    return candles

            except asyncio.TimeoutError:
                logger.error(f"{instrument}: Request timeout (attempt {attempt + 1})")
                if attempt == self.MAX_RETRIES - 1:
                    return []
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"{instrument}: Error fetching data (attempt {attempt + 1}): {e}")
                if attempt == self.MAX_RETRIES - 1:
                    return []
                await asyncio.sleep(2 ** attempt)

        return []

    def upsert_to_db(self, instrument: str, expiry_date: str, candles: List[Dict]):
        """
        Insert candles into database (idempotent).

        Args:
            instrument: Instrument name
            expiry_date: Expiry date (YYYY-MM-DD)
            candles: List of candle dictionaries
        """
        if not candles:
            return

        cur = self.conn.cursor()

        query = """
        INSERT INTO futures_ohlcv
        (timestamp, instrument, expiry_date, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, instrument) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
        """

        rows = [
            (
                c['timestamp'],
                instrument,
                datetime.strptime(expiry_date, "%Y-%m-%d").date(),
                c['open'],
                c['high'],
                c['low'],
                c['close'],
                c['volume']
            )
            for c in candles
        ]

        try:
            cur.executemany(query, rows)
            self.conn.commit()
            self.total_candles += len(rows)
        except Exception as e:
            logger.error(f"{instrument}: Database error: {e}")
            self.conn.rollback()

    async def backfill_instrument(
        self,
        session: aiohttp.ClientSession,
        instrument_info: Dict
    ) -> int:
        """
        Backfill single futures instrument.

        Args:
            session: aiohttp client session
            instrument_info: Instrument metadata dict

        Returns:
            Number of candles backfilled
        """
        instrument = instrument_info['instrument']
        expiry_date = instrument_info['expiry_date']
        estimated_start = instrument_info['estimated_start']

        logger.info(f"Starting {instrument} (expiry: {expiry_date})")

        # Convert dates to timestamps
        start_ts = int(datetime.strptime(estimated_start, "%Y-%m-%d")
                      .replace(tzinfo=timezone.utc).timestamp())
        end_ts = int(datetime.strptime(expiry_date, "%Y-%m-%d")
                    .replace(tzinfo=timezone.utc).timestamp())

        # Add buffer: fetch until day after expiry (settlement data)
        end_ts += 86400

        total_candles = 0
        current_ts = start_ts

        while current_ts < end_ts:
            # Calculate chunk end (5000 minutes max)
            chunk_end = min(current_ts + (self.MAX_CANDLES_PER_CALL * 60), end_ts)

            # Fetch chunk
            candles = await self.fetch_ohlcv_chunk(session, instrument, current_ts, chunk_end)

            if candles:
                # Insert to database
                self.upsert_to_db(instrument, expiry_date, candles)
                total_candles += len(candles)

                # Progress log every 50k candles
                if total_candles % 50000 == 0:
                    logger.info(f"{instrument}: {total_candles:,} candles so far...")

            # Rate limiting
            await asyncio.sleep(self.RATE_LIMIT_DELAY)

            # Move to next chunk
            current_ts = chunk_end

            # If no candles returned and we're early in the range, skip ahead
            if not candles and current_ts < start_ts + (30 * 86400):  # First 30 days
                logger.debug(f"{instrument}: No data in early range, skipping ahead...")
                current_ts = start_ts + (30 * 86400)

        if total_candles == 0:
            logger.warning(f"{instrument}: ⚠️ No data found (might be delisted or no trading)")
            self.failed_instruments.append(instrument)
        else:
            logger.info(f"{instrument}: ✅ Complete - {total_candles:,} candles")

        return total_candles

    async def backfill_all(self, futures_list: List[Dict], currency_filter: Optional[str] = None):
        """
        Backfill all futures instruments.

        Args:
            futures_list: List of futures instrument metadata
            currency_filter: Optional currency filter ('BTC' or 'ETH')
        """
        # Filter by currency if specified
        if currency_filter:
            futures_list = [f for f in futures_list if f['currency'] == currency_filter]
            logger.info(f"Filtered to {len(futures_list)} {currency_filter} futures")

        logger.info(f"Starting backfill for {len(futures_list)} instruments...")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for i, future_info in enumerate(futures_list, 1):
                logger.info(f"\n[{i}/{len(futures_list)}] Processing {future_info['instrument']}")

                try:
                    await self.backfill_instrument(session, future_info)
                except Exception as e:
                    logger.error(f"{future_info['instrument']}: Fatal error: {e}", exc_info=True)
                    self.failed_instruments.append(future_info['instrument'])

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Backfill Complete!")
        logger.info("=" * 60)
        logger.info(f"Total candles inserted: {self.total_candles:,}")
        logger.info(f"Total API calls: {self.total_api_calls:,}")
        logger.info(f"Successful instruments: {len(futures_list) - len(self.failed_instruments)}/{len(futures_list)}")

        if self.failed_instruments:
            logger.warning(f"\nFailed/Empty instruments ({len(self.failed_instruments)}):")
            for inst in self.failed_instruments[:20]:  # Show first 20
                logger.warning(f"  - {inst}")
            if len(self.failed_instruments) > 20:
                logger.warning(f"  ... and {len(self.failed_instruments) - 20} more")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


async def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Backfill futures OHLCV')
    parser.add_argument('--all', action='store_true', help='Backfill all instruments')
    parser.add_argument('--instruments', help='Comma-separated list of instruments')
    parser.add_argument('--currency', choices=['BTC', 'ETH'], help='Filter by currency')

    args = parser.parse_args()

    # Load futures list
    with open('data/historical_futures_list.json') as f:
        futures_list = json.load(f)

    # Filter instruments if specified
    if args.instruments:
        instrument_names = args.instruments.split(',')
        futures_list = [f for f in futures_list if f['instrument'] in instrument_names]
        logger.info(f"Filtered to {len(futures_list)} specified instruments")
    elif not args.all and not args.currency:
        logger.error("Must specify --all, --instruments, or --currency")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Futures Historical Backfill Started")
    logger.info("=" * 60)
    logger.info(f"Total instruments to backfill: {len(futures_list)}")
    logger.info("")

    backfiller = FuturesBackfiller()

    try:
        await backfiller.backfill_all(futures_list, currency_filter=args.currency)
    except KeyboardInterrupt:
        logger.warning("\n\nBackfill interrupted by user")
        logger.info(f"Progress: {backfiller.total_candles:,} candles inserted so far")
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise
    finally:
        backfiller.close()


if __name__ == '__main__':
    asyncio.run(main())
