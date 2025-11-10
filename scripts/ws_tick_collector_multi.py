"""
WebSocket Tick Collector - Multi-Currency Options Real-Time Data Collector
Supports BTC, ETH, and future currencies

This is the main WebSocket collector that subscribes to top N options
and streams quote/trade ticks to the database.

Features:
- Multi-currency support (BTC, ETH, SOL, etc.)
- Subscribe to book.{instrument}.100ms (quotes) and trades.{instrument}.100ms
- Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, max 60s)
- In-memory buffering (200k quotes, 100k trades)
- Batch database writes (every 3s or 80% buffer full)
- Graceful shutdown (SIGTERM, SIGINT)
- Heartbeat monitoring (warn if no ticks for 10s)

Usage:
    # Set environment variable CURRENCY=BTC or CURRENCY=ETH
    python -m scripts.ws_tick_collector_multi
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import websockets
from dotenv import load_dotenv

# Import our custom modules
from scripts.instrument_fetcher_multi import MultiCurrencyInstrumentFetcher
from scripts.tick_buffer import TickBuffer
from scripts.tick_writer_multi import MultiCurrencyTickWriter
from scripts.instrument_expiry_checker import filter_expired_instruments, get_next_expiry_time

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
CURRENCY = os.getenv('CURRENCY', 'ETH').upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/ws_tick_collector_{CURRENCY.lower()}.log')
    ]
)
logger = logging.getLogger(__name__)


class MultiCurrencyOrderbookSnapshotFetcher:
    """
    Fetch orderbook snapshots via REST API and populate database (multi-currency).
    """

    def __init__(self, database_url: str, currency: str, rest_api_url: str = "https://www.deribit.com/api/v2"):
        self.database_url = database_url
        self.currency = currency.upper()
        self.rest_api_url = rest_api_url
        self.writer = MultiCurrencyTickWriter(database_url, currency=currency)
        logger.info(f"MultiCurrencyOrderbookSnapshotFetcher initialized for {self.currency}")

    async def fetch_and_populate(self, instruments: List[str], save_full_depth: bool = False) -> Dict[str, int]:
        """Fetch orderbook snapshots for all instruments and populate database."""
        import aiohttp

        logger.info(f"Fetching {self.currency} orderbook snapshots for {len(instruments)} instruments...")

        await self.writer.connect()

        stats = {
            'instruments_fetched': 0,
            'quotes_populated': 0,
            'depth_snapshots': 0,
            'errors': 0,
            'instruments_with_data': 0,
            'instruments_without_data': 0
        }

        async with aiohttp.ClientSession() as session:
            batch_size = 10
            for i in range(0, len(instruments), batch_size):
                batch = instruments[i:i + batch_size]

                tasks = [
                    self._fetch_orderbook(session, instrument, save_full_depth)
                    for instrument in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                quotes = []
                depth_snapshots = []
                for instrument, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.error(f"Error fetching {instrument}: {result}")
                        stats['errors'] += 1
                    elif result is not None:
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

                if quotes:
                    await self.writer.write_quotes(quotes)
                    stats['quotes_populated'] += len(quotes)

                if depth_snapshots:
                    await self.writer.write_depth_snapshots(depth_snapshots)
                    stats['depth_snapshots'] += len(depth_snapshots)

                if i + batch_size < len(instruments):
                    await asyncio.sleep(0.5)

        logger.info(
            f"✅ {self.currency} snapshot complete: {stats['instruments_fetched']} instruments fetched, "
            f"{stats['quotes_populated']} quotes"
        )

        await self.writer.close()
        return stats

    async def _fetch_orderbook(self, session, instrument: str, save_full_depth: bool):
        """Fetch orderbook for a single instrument via REST API."""
        try:
            import aiohttp

            url = f"{self.rest_api_url}/public/get_order_book"
            params = {
                'instrument_name': instrument,
                'depth': 20 if save_full_depth else 1
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                if 'result' not in data:
                    return None

                result = data['result']
                bids = result.get('bids', [])
                asks = result.get('asks', [])
                mark_price = result.get('mark_price')
                underlying_price = result.get('underlying_price')

                best_bid_price = float(bids[0][0]) if bids else None
                best_bid_amount = float(bids[0][1]) if bids else None
                best_ask_price = float(asks[0][0]) if asks else None
                best_ask_amount = float(asks[0][1]) if asks else None

                if not bids and not asks and mark_price is None:
                    return None

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

                depth = None
                if save_full_depth:
                    bids_json = [{"price": float(b[0]), "amount": float(b[1])} for b in bids] if bids else []
                    asks_json = [{"price": float(a[0]), "amount": float(a[1])} for a in asks] if asks else []

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

                return (quote, depth)

        except Exception as e:
            logger.error(f"Exception fetching {instrument}: {e}")
            return None


class WebSocketTickCollector:
    """
    Main WebSocket collector for multi-currency options tick data.
    """

    def __init__(
        self,
        ws_url: str,
        database_url: str,
        currency: str = "ETH",
        top_n_instruments: int = 50,
        buffer_size_quotes: int = 200000,
        buffer_size_trades: int = 100000,
        flush_interval_sec: int = 3
    ):
        """Initialize WebSocket tick collector with currency support."""
        self.ws_url = ws_url
        self.database_url = database_url
        self.currency = currency.upper()
        self.top_n_instruments = top_n_instruments
        self.flush_interval_sec = flush_interval_sec

        # Components (currency-specific)
        self.instrument_fetcher = MultiCurrencyInstrumentFetcher(currency=self.currency)
        self.buffer = TickBuffer(
            max_quotes=buffer_size_quotes,
            max_trades=buffer_size_trades,
            max_depth=50000
        )
        self.writer = MultiCurrencyTickWriter(database_url, currency=self.currency)

        # State
        self.instruments: List[str] = []
        self.subscribed_channels: Set[str] = set()
        self.ws = None
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60

        # Heartbeat monitoring
        self.last_tick_time: Optional[datetime] = None
        self.heartbeat_timeout_sec = 10
        self.no_ticks_refresh_threshold_sec = 300  # Refresh instruments if no ticks for 5 minutes

        # Statistics
        self.stats = {
            'connection_attempts': 0,
            'reconnections': 0,
            'ticks_processed': 0,
            'quotes_received': 0,
            'trades_received': 0,
            'depth_received': 0,
            'errors': 0
        }

        logger.info(
            f"WebSocketTickCollector initialized for {self.currency}: "
            f"top_n={top_n_instruments}, flush_interval={flush_interval_sec}s"
        )

    async def start(self):
        """Start the collector (main entry point)."""
        logger.info(f"Starting {self.currency} WebSocket tick collector...")

        try:
            # Connect to database
            await self.writer.connect()

            # Fetch instruments (only if not already set by orchestrator)
            if not self.instruments:
                logger.info(f"Fetching top {self.top_n_instruments} {self.currency} options...")
                self.instruments = await self.instrument_fetcher.get_top_n_options(
                    n=self.top_n_instruments
                )
            else:
                logger.info(f"Using pre-assigned instruments: {len(self.instruments)} instruments")

            logger.info(f"Subscribed instruments: {len(self.instruments)}")
            logger.debug(f"First 5: {self.instruments[:5]}")

            # Fetch initial orderbook snapshot via REST API
            logger.info(f"Fetching initial {self.currency} orderbook snapshot via REST API...")
            snapshot_fetcher = MultiCurrencyOrderbookSnapshotFetcher(
                database_url=self.database_url,
                currency=self.currency,
                rest_api_url="https://www.deribit.com/api/v2"
            )
            snapshot_stats = await snapshot_fetcher.fetch_and_populate(
                self.instruments,
                save_full_depth=True
            )
            logger.info(
                f"Initial snapshot complete: {snapshot_stats['quotes_populated']} quotes, "
                f"{snapshot_stats['depth_snapshots']} depth snapshots"
            )

            # Set running flag
            self.running = True

            # Start tasks
            tasks = [
                asyncio.create_task(self._websocket_loop()),
                asyncio.create_task(self._flush_loop()),
                asyncio.create_task(self._heartbeat_monitor()),
                asyncio.create_task(self._stats_logger()),
                asyncio.create_task(self._periodic_snapshot_loop()),
                asyncio.create_task(self._instrument_refresh_loop())
            ]

            # Wait for all tasks
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Fatal error in {self.currency} collector: {e}", exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the collector gracefully."""
        logger.info(f"Stopping {self.currency} WebSocket tick collector...")
        self.running = False

        logger.info("Flushing remaining buffers...")
        await self._flush_buffers()

        if self.ws:
            await self.ws.close()

        await self.writer.close()

        logger.info(f"{self.currency} WebSocket tick collector stopped")

    async def _websocket_loop(self):
        """Main WebSocket connection loop with auto-reconnect."""
        while self.running:
            try:
                self.stats['connection_attempts'] += 1

                logger.info(f"Connecting to WebSocket: {self.ws_url}")
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=10
                ) as ws:
                    self.ws = ws
                    logger.info(f"{self.currency} WebSocket connected successfully")

                    self.reconnect_delay = 1

                    await self._subscribe_to_instruments()
                    await self._process_messages()

            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
                self.stats['errors'] += 1
                await self._handle_reconnect()

            except Exception as e:
                logger.error(f"Unexpected error in WebSocket loop: {e}", exc_info=True)
                self.stats['errors'] += 1
                await self._handle_reconnect()

    async def _subscribe_to_instruments(self):
        """Subscribe to ticker and trade channels for all instruments."""
        channels = []

        for instrument in self.instruments:
            # Use ticker channel instead of book to get Greeks and complete data
            channels.append(f"ticker.{instrument}.100ms")
            channels.append(f"trades.{instrument}.100ms")

        subscription_msg = {
            "jsonrpc": "2.0",
            "method": "public/subscribe",
            "params": {
                "channels": channels
            },
            "id": 1
        }

        logger.info(f"Subscribing to {len(channels)} channels ({len(self.instruments)} instruments)...")
        await self.ws.send(json.dumps(subscription_msg))

        response = await self.ws.recv()
        response_data = json.loads(response)

        if 'result' in response_data:
            self.subscribed_channels = set(response_data['result'])
            logger.info(f"Successfully subscribed to {len(self.subscribed_channels)} channels")
        else:
            logger.error(f"Subscription failed: {response_data}")
            raise Exception("Failed to subscribe to channels")

    async def _process_messages(self):
        """Process incoming WebSocket messages."""
        async for message in self.ws:
            try:
                data = json.loads(message)

                if 'params' in data:
                    channel = data['params'].get('channel', '')
                    tick_data = data['params'].get('data', {})

                    self.last_tick_time = datetime.now()

                    if channel.startswith('ticker.'):
                        await self._handle_quote_tick(tick_data)
                    elif channel.startswith('trades.'):
                        await self._handle_trade_tick(tick_data)

                    self.stats['ticks_processed'] += 1

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {e}")
                self.stats['errors'] += 1
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                self.stats['errors'] += 1

    async def _handle_quote_tick(self, data: Dict):
        """Handle quote tick from ticker.{instrument}.100ms channel with Greeks."""
        try:
            # Extract Greeks from nested dictionary
            greeks = data.get('greeks', {})

            quote = {
                'timestamp': datetime.fromtimestamp(data['timestamp'] / 1000),
                'instrument_name': data['instrument_name'],
                'best_bid_price': data.get('best_bid_price'),
                'best_bid_amount': data.get('best_bid_amount'),
                'best_ask_price': data.get('best_ask_price'),
                'best_ask_amount': data.get('best_ask_amount'),
                'underlying_price': data.get('underlying_price'),
                'mark_price': data.get('mark_price'),
                # Greek values from data['greeks']
                'delta': greeks.get('delta'),
                'gamma': greeks.get('gamma'),
                'theta': greeks.get('theta'),
                'vega': greeks.get('vega'),
                'rho': greeks.get('rho'),
                # IV fields
                'implied_volatility': data.get('mark_iv'),  # Use mark_iv as primary IV
                'bid_iv': data.get('bid_iv'),
                'ask_iv': data.get('ask_iv'),
                'mark_iv': data.get('mark_iv'),
                # Additional fields
                'open_interest': data.get('open_interest'),
                'last_price': data.get('last_price')
            }

            self.buffer.add_quote(quote)
            self.stats['quotes_received'] += 1

        except Exception as e:
            logger.error(f"Failed to process quote tick: {e}")
            self.stats['errors'] += 1

    async def _handle_trade_tick(self, data: Dict):
        """Handle trade tick from trades.{instrument}.100ms channel."""
        try:
            trades = data if isinstance(data, list) else [data]

            for trade_data in trades:
                trade = {
                    'timestamp': datetime.fromtimestamp(trade_data['timestamp'] / 1000),
                    'instrument_name': trade_data['instrument_name'],
                    'trade_id': trade_data['trade_id'],
                    'price': trade_data['price'],
                    'amount': trade_data['amount'],
                    'direction': trade_data['direction'],
                    'iv': trade_data.get('iv'),
                    'index_price': trade_data.get('index_price')
                }

                self.buffer.add_trade(trade)
                self.stats['trades_received'] += 1

        except Exception as e:
            logger.error(f"Failed to process trade tick: {e}")
            self.stats['errors'] += 1

    async def _flush_loop(self):
        """Periodic buffer flush loop."""
        while self.running:
            try:
                await asyncio.sleep(self.flush_interval_sec)

                if self.buffer.should_flush() or self.buffer.get_quote_count() > 0 or self.buffer.get_trade_count() > 0:
                    await self._flush_buffers()

            except Exception as e:
                logger.error(f"Error in flush loop: {e}", exc_info=True)

    async def _flush_buffers(self):
        """Flush buffers to database."""
        try:
            quotes, trades, depth = self.buffer.get_and_clear()

            if quotes:
                await self.writer.write_quotes(quotes)

            if trades:
                await self.writer.write_trades(trades)

            if depth:
                await self.writer.write_depth_snapshots(depth)

        except Exception as e:
            logger.error(f"Failed to flush buffers: {e}", exc_info=True)
            self.stats['errors'] += 1

    async def _heartbeat_monitor(self):
        """Monitor heartbeat and warn if no ticks received."""
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_timeout_sec)

                if self.last_tick_time:
                    time_since_last_tick = (datetime.now() - self.last_tick_time).total_seconds()

                    if time_since_last_tick > self.heartbeat_timeout_sec:
                        logger.warning(
                            f"No {self.currency} ticks received for {time_since_last_tick:.0f}s"
                        )

                    # Trigger instrument refresh if no ticks for too long (likely expired)
                    if time_since_last_tick > self.no_ticks_refresh_threshold_sec:
                        logger.error(
                            f"No ticks for {time_since_last_tick:.0f}s - instruments may have expired! "
                            f"Triggering instrument refresh..."
                        )
                        await self._refresh_instruments()

            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}", exc_info=True)

    async def _stats_logger(self):
        """Log statistics every 60 seconds."""
        while self.running:
            try:
                await asyncio.sleep(60)

                buffer_stats = self.buffer.get_stats_summary()
                writer_stats = self.writer.get_stats()

                logger.info(
                    f"[{self.currency}] STATS | Ticks: {self.stats['ticks_processed']} "
                    f"| Quotes: {self.stats['quotes_received']} "
                    f"| Trades: {self.stats['trades_received']} "
                    f"| Errors: {self.stats['errors']} "
                    f"| Buffer: Q={buffer_stats['quotes']['utilization_pct']:.1f}% "
                    f"T={buffer_stats['trades']['utilization_pct']:.1f}% "
                    f"| DB Writes: Q={writer_stats['quotes_written']} T={writer_stats['trades_written']}"
                )

            except Exception as e:
                logger.error(f"Error in stats logger: {e}", exc_info=True)

    async def _handle_reconnect(self):
        """Handle reconnection with exponential backoff."""
        if not self.running:
            return

        self.stats['reconnections'] += 1

        logger.warning(f"Reconnecting in {self.reconnect_delay}s... (attempt {self.stats['reconnections']})")
        await asyncio.sleep(self.reconnect_delay)

        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def _periodic_snapshot_loop(self):
        """Fetch periodic REST API snapshots to ensure complete pricing data."""
        snapshot_interval_sec = int(os.getenv('SNAPSHOT_INTERVAL_SEC', 300))

        logger.info(f"Periodic snapshot loop started for {self.currency} (interval: {snapshot_interval_sec}s)")

        while self.running:
            try:
                await asyncio.sleep(snapshot_interval_sec)

                if not self.running:
                    break

                logger.info(f"Fetching periodic {self.currency} REST API snapshot...")

                snapshot_fetcher = MultiCurrencyOrderbookSnapshotFetcher(
                    database_url=self.database_url,
                    currency=self.currency,
                    rest_api_url="https://www.deribit.com/api/v2"
                )

                snapshot_stats = await snapshot_fetcher.fetch_and_populate(
                    self.instruments,
                    save_full_depth=True
                )

                logger.info(
                    f"Periodic {self.currency} snapshot complete: {snapshot_stats['quotes_populated']} quotes, "
                    f"{snapshot_stats['instruments_with_data']} instruments with data"
                )

            except Exception as e:
                logger.error(f"Error in periodic snapshot loop: {e}", exc_info=True)

    async def _instrument_refresh_loop(self):
        """
        Periodic instrument refresh loop.
        Checks for expired instruments and refreshes the subscription list.
        Runs every hour or at next expiry time (whichever is sooner).
        """
        refresh_interval_sec = int(os.getenv('INSTRUMENT_REFRESH_INTERVAL_SEC', 3600))  # Default 1 hour

        logger.info(f"Instrument refresh loop started for {self.currency} (interval: {refresh_interval_sec}s)")

        while self.running:
            try:
                # Calculate sleep time until next check
                # Check sooner if we know instruments are expiring soon
                next_expiry = get_next_expiry_time(self.instruments)
                if next_expiry:
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                    seconds_until_expiry = (next_expiry - now).total_seconds()

                    # Check 1 minute after expiry to give exchange time to update
                    sleep_time = min(refresh_interval_sec, max(60, seconds_until_expiry + 60))
                else:
                    sleep_time = refresh_interval_sec

                logger.info(f"Next instrument refresh in {sleep_time/60:.1f} minutes")

                await asyncio.sleep(sleep_time)

                if not self.running:
                    break

                # Check if current instruments have expired
                active_instruments = filter_expired_instruments(self.instruments, buffer_minutes=5)

                if len(active_instruments) < len(self.instruments):
                    expired_count = len(self.instruments) - len(active_instruments)
                    logger.warning(
                        f"{expired_count} instruments expired! "
                        f"Active: {len(active_instruments)}, Expired: {expired_count}"
                    )
                    logger.info("Triggering instrument refresh due to expiry...")
                    await self._refresh_instruments()
                else:
                    logger.info(f"All {len(self.instruments)} instruments still active")

            except Exception as e:
                logger.error(f"Error in instrument refresh loop: {e}", exc_info=True)

    async def _refresh_instruments(self):
        """
        Refresh instrument list and resubscribe to WebSocket.
        Called when instruments expire or no ticks are received for long time.
        """
        try:
            logger.info(f"🔄 Refreshing {self.currency} instruments...")

            # Fetch new top instruments
            new_instruments = await self.instrument_fetcher.get_top_n_options(
                n=self.top_n_instruments
            )

            # Filter out expired ones
            new_instruments = filter_expired_instruments(new_instruments, buffer_minutes=5)

            if not new_instruments:
                logger.error("No active instruments found! Will retry in next refresh cycle.")
                return

            # Check if instruments changed
            old_set = set(self.instruments)
            new_set = set(new_instruments)

            added = new_set - old_set
            removed = old_set - new_set
            unchanged = old_set & new_set

            logger.info(
                f"Instrument changes: {len(added)} added, {len(removed)} removed, {len(unchanged)} unchanged"
            )

            if added:
                logger.info(f"New instruments: {list(added)[:5]}...")
            if removed:
                logger.info(f"Removed instruments: {list(removed)[:5]}...")

            # Update instrument list
            self.instruments = new_instruments

            # Close existing WebSocket connection to trigger reconnect with new subscriptions
            if self.ws:
                logger.info("Closing WebSocket to refresh subscriptions...")
                await self.ws.close()
                # The websocket_loop will automatically reconnect and resubscribe

            # Reset last tick time so heartbeat doesn't trigger another refresh immediately
            self.last_tick_time = datetime.now()

            logger.info(f"✅ Instrument refresh complete: {len(self.instruments)} active instruments")

        except Exception as e:
            logger.error(f"Failed to refresh instruments: {e}", exc_info=True)
            self.stats['errors'] += 1


async def main():
    """Main entry point for WebSocket tick collector."""
    # Load configuration from environment
    WS_URL = os.getenv('DERIBIT_WS_URL', 'wss://www.deribit.com/ws/api/v2')
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')
    CURRENCY = os.getenv('CURRENCY', 'ETH').upper()
    BUFFER_SIZE_QUOTES = int(os.getenv('BUFFER_SIZE_QUOTES', 200000))
    BUFFER_SIZE_TRADES = int(os.getenv('BUFFER_SIZE_TRADES', 100000))
    FLUSH_INTERVAL_SEC = int(os.getenv('FLUSH_INTERVAL_SEC', 3))
    TOP_N_INSTRUMENTS = int(os.getenv('TOP_N_INSTRUMENTS', 50))

    logger.info(f"Starting multi-currency collector for {CURRENCY}")

    # Create collector
    collector = WebSocketTickCollector(
        ws_url=WS_URL,
        database_url=DATABASE_URL,
        currency=CURRENCY,
        top_n_instruments=TOP_N_INSTRUMENTS,
        buffer_size_quotes=BUFFER_SIZE_QUOTES,
        buffer_size_trades=BUFFER_SIZE_TRADES,
        flush_interval_sec=FLUSH_INTERVAL_SEC
    )

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        asyncio.create_task(collector.stop())

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start collector
    try:
        await collector.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await collector.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await collector.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    # Run collector
    asyncio.run(main())
