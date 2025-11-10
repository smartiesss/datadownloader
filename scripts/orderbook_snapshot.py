"""
Orderbook Snapshot Fetcher - Fetch Initial Orderbook via REST API

This module fetches the current orderbook for all instruments via Deribit REST API
and populates the database. This provides the initial snapshot, and then WebSocket
updates can be applied on top.

This solves the NULL data issue where WebSocket may only send updates/deltas
instead of full orderbook snapshots.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict
import aiohttp

from scripts.tick_writer import TickWriter

logger = logging.getLogger(__name__)


class OrderbookSnapshotFetcher:
    """
    Fetch orderbook snapshots via REST API and populate database.

    This is used to get initial orderbook data before starting WebSocket,
    since WebSocket may only send delta updates.
    """

    def __init__(self, database_url: str, rest_api_url: str = "https://www.deribit.com/api/v2"):
        """
        Initialize snapshot fetcher.

        Args:
            database_url: PostgreSQL connection URL
            rest_api_url: Deribit REST API URL (default: production)
        """
        self.database_url = database_url
        self.rest_api_url = rest_api_url
        self.writer = TickWriter(database_url)

        logger.info(f"OrderbookSnapshotFetcher initialized: rest_api={rest_api_url}")

    async def fetch_and_populate(self, instruments: List[str], save_full_depth: bool = False) -> Dict[str, int]:
        """
        Fetch orderbook snapshots for all instruments and populate database.

        Args:
            instruments: List of instrument names (e.g., ['ETH-10NOV25-3200-C', ...])
            save_full_depth: If True, save full orderbook depth to eth_option_orderbook_depth table

        Returns:
            Dictionary with stats:
            {
                'instruments_fetched': 50,
                'quotes_populated': 50,
                'depth_snapshots': 50,  # Only if save_full_depth=True
                'errors': 0
            }
        """
        logger.info(f"Fetching orderbook snapshots for {len(instruments)} instruments (full_depth={save_full_depth})...")

        # Connect to database
        await self.writer.connect()

        stats = {
            'instruments_fetched': 0,
            'quotes_populated': 0,
            'depth_snapshots': 0,
            'errors': 0,
            'instruments_with_data': 0,
            'instruments_without_data': 0
        }

        self.save_full_depth = save_full_depth

        # Fetch orderbooks (with rate limiting)
        async with aiohttp.ClientSession() as session:
            # Process in batches to avoid overwhelming API
            batch_size = 10
            for i in range(0, len(instruments), batch_size):
                batch = instruments[i:i + batch_size]

                # Fetch batch concurrently
                tasks = [
                    self._fetch_orderbook(session, instrument)
                    for instrument in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                quotes = []
                depth_snapshots = []
                for instrument, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.error(f"Error fetching {instrument}: {result}")
                        stats['errors'] += 1
                    elif result is not None:
                        # Result is a tuple: (quote_dict, depth_dict)
                        quote_dict, depth_dict = result
                        if quote_dict:
                            quotes.append(quote_dict)
                        if depth_dict:
                            depth_snapshots.append(depth_dict)
                        stats['instruments_fetched'] += 1
                        stats['instruments_with_data'] += 1
                    else:
                        stats['instruments_fetched'] += 1
                        stats['instruments_without_data'] += 1

                # Write batch to database
                if quotes:
                    await self.writer.write_quotes(quotes)
                    stats['quotes_populated'] += len(quotes)

                if depth_snapshots and self.save_full_depth:
                    await self.writer.write_depth_snapshots(depth_snapshots)
                    stats['depth_snapshots'] += len(depth_snapshots)

                logger.info(
                    f"Progress: {stats['instruments_fetched']}/{len(instruments)} instruments, "
                    f"{stats['quotes_populated']} quotes, {stats['depth_snapshots']} depth snapshots"
                )

                # Rate limiting: wait between batches
                if i + batch_size < len(instruments):
                    await asyncio.sleep(0.5)

        logger.info(
            f"✅ Snapshot complete: {stats['instruments_fetched']} instruments fetched, "
            f"{stats['quotes_populated']} quotes populated, "
            f"{stats['instruments_with_data']} with data, "
            f"{stats['instruments_without_data']} without data, "
            f"{stats['errors']} errors"
        )

        # Close database connection
        await self.writer.close()

        return stats

    async def _fetch_orderbook(self, session: aiohttp.ClientSession, instrument: str):
        """
        Fetch orderbook for a single instrument via REST API.

        Args:
            session: aiohttp session
            instrument: Instrument name (e.g., 'ETH-10NOV25-3200-C')

        Returns:
            Tuple of (quote_dict, depth_dict) ready for database insertion, or None if no data
            - quote_dict: Best bid/ask for eth_option_quotes table
            - depth_dict: Full orderbook depth for eth_option_orderbook_depth table
        """
        try:
            url = f"{self.rest_api_url}/public/get_order_book"
            params = {
                'instrument_name': instrument,
                'depth': 20 if self.save_full_depth else 1  # Fetch 20 levels if full depth requested
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} for {instrument}")
                    return None

                data = await response.json()

                if 'result' not in data:
                    logger.warning(f"No result in response for {instrument}")
                    return None

                result = data['result']

                # Check if we have bid/ask data
                bids = result.get('bids', [])
                asks = result.get('asks', [])

                # Extract mark_price and underlying_price (always available)
                mark_price = result.get('mark_price')
                underlying_price = result.get('underlying_price')

                # Extract best bid/ask (may be empty for illiquid options)
                best_bid_price = float(bids[0][0]) if bids else None
                best_bid_amount = float(bids[0][1]) if bids else None
                best_ask_price = float(asks[0][0]) if asks else None
                best_ask_amount = float(asks[0][1]) if asks else None

                # If no bid/ask AND no mark_price, skip (truly dead instrument)
                if not bids and not asks and mark_price is None:
                    logger.debug(f"No data at all for {instrument} - skipping")
                    return None

                # Build quote dictionary (for eth_option_quotes table)
                quote = {
                    'timestamp': datetime.fromtimestamp(result['timestamp'] / 1000),
                    'instrument_name': result['instrument_name'],
                    'best_bid_price': best_bid_price,
                    'best_bid_amount': best_bid_amount,
                    'best_ask_price': best_ask_price,
                    'best_ask_amount': best_ask_amount,
                    'underlying_price': underlying_price,
                    'mark_price': mark_price
                }

                # Build depth dictionary (for eth_option_orderbook_depth table)
                depth = None
                if self.save_full_depth:
                    # Convert Deribit format [[price, amount], ...] to JSONB format
                    bids_json = [{"price": float(bid[0]), "amount": float(bid[1])} for bid in bids] if bids else []
                    asks_json = [{"price": float(ask[0]), "amount": float(ask[1])} for ask in asks] if asks else []

                    depth = {
                        'timestamp': datetime.fromtimestamp(result['timestamp'] / 1000),
                        'instrument': result['instrument_name'],
                        'bids': bids_json,
                        'asks': asks_json,
                        'mark_price': mark_price,
                        'underlying_price': underlying_price,
                        'open_interest': result.get('open_interest'),
                        'volume_24h': result.get('stats', {}).get('volume')
                    }

                logger.debug(
                    f"{instrument}: bid={best_bid_price}, ask={best_ask_price}, "
                    f"mark={mark_price}, depth_levels={len(bids)}/{len(asks)}"
                )

                return (quote, depth)

        except Exception as e:
            logger.error(f"Exception fetching {instrument}: {e}", exc_info=True)
            return None


async def main():
    """Test the snapshot fetcher."""
    import os
    from dotenv import load_dotenv
    from scripts.instrument_fetcher import InstrumentFetcher

    load_dotenv()

    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')

    # Fetch instruments
    instrument_fetcher = InstrumentFetcher()
    instruments = await instrument_fetcher.get_top_n_eth_options(n=50)

    print(f"📊 Fetching orderbook snapshots for {len(instruments)} instruments...")

    # Fetch and populate
    snapshot_fetcher = OrderbookSnapshotFetcher(DATABASE_URL)
    stats = await snapshot_fetcher.fetch_and_populate(instruments)

    print(f"\n✅ Complete!")
    print(f"   Instruments fetched: {stats['instruments_fetched']}")
    print(f"   Quotes populated: {stats['quotes_populated']}")
    print(f"   Instruments with data: {stats['instruments_with_data']}")
    print(f"   Instruments without data: {stats['instruments_without_data']}")
    print(f"   Errors: {stats['errors']}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())
