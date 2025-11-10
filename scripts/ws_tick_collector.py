"""
WebSocket Tick Collector - ETH Options Real-Time Data Collector
Task: T-001
Acceptance Criteria: AC-001 (Data completeness >98%), AC-005 (Auto-recovery)

This is the main WebSocket collector that subscribes to top 50 ETH options
and streams quote/trade ticks to the database.

Features:
- Multi-connection support (designed to scale to 3, starts with 1)
- Subscribe to book.{instrument}.100ms (quotes) and trades.{instrument}.100ms
- Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, max 60s)
- In-memory buffering (200k quotes, 100k trades)
- Batch database writes (every 3s or 80% buffer full)
- Graceful shutdown (SIGTERM, SIGINT)
- Heartbeat monitoring (warn if no ticks for 10s)

Usage:
    python -m scripts.ws_tick_collector
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
from scripts.instrument_fetcher import InstrumentFetcher
from scripts.tick_buffer import TickBuffer
from scripts.tick_writer import TickWriter
from scripts.orderbook_snapshot import OrderbookSnapshotFetcher

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/ws_tick_collector.log')
    ]
)
logger = logging.getLogger(__name__)


class WebSocketTickCollector:
    """
    Main WebSocket collector for ETH options tick data.

    Features:
    - Manages WebSocket connection lifecycle
    - Handles subscription to top N instruments
    - Auto-reconnect with exponential backoff
    - Periodic buffer flushes to database
    - Graceful shutdown on SIGTERM/SIGINT
    - Heartbeat monitoring
    """

    def __init__(
        self,
        ws_url: str,
        database_url: str,
        top_n_instruments: int = 50,
        buffer_size_quotes: int = 200000,
        buffer_size_trades: int = 100000,
        flush_interval_sec: int = 3
    ):
        """
        Initialize WebSocket tick collector.

        Args:
            ws_url: Deribit WebSocket URL
            database_url: PostgreSQL connection URL
            top_n_instruments: Number of top instruments to subscribe to
            buffer_size_quotes: Max quotes in buffer before forced flush
            buffer_size_trades: Max trades in buffer before forced flush
            flush_interval_sec: Flush interval in seconds
        """
        self.ws_url = ws_url
        self.database_url = database_url
        self.top_n_instruments = top_n_instruments
        self.flush_interval_sec = flush_interval_sec

        # Components
        self.instrument_fetcher = InstrumentFetcher()
        self.buffer = TickBuffer(
            max_quotes=buffer_size_quotes,
            max_trades=buffer_size_trades,
            max_depth=50000  # Buffer for full depth snapshots
        )
        self.writer = TickWriter(database_url)

        # State
        self.instruments: List[str] = []
        self.subscribed_channels: Set[str] = set()
        self.ws = None
        self.running = False
        self.reconnect_delay = 1  # Start with 1 second
        self.max_reconnect_delay = 60  # Cap at 60 seconds

        # Heartbeat monitoring
        self.last_tick_time: Optional[datetime] = None
        self.heartbeat_timeout_sec = 10

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
            f"WebSocketTickCollector initialized: "
            f"ws_url={ws_url}, top_n={top_n_instruments}, "
            f"flush_interval={flush_interval_sec}s"
        )

    async def start(self):
        """Start the collector (main entry point)."""
        logger.info("Starting WebSocket tick collector...")

        try:
            # Connect to database
            await self.writer.connect()

            # Fetch top instruments
            logger.info(f"Fetching top {self.top_n_instruments} ETH options...")
            self.instruments = await self.instrument_fetcher.get_top_n_eth_options(
                n=self.top_n_instruments
            )
            logger.info(f"Subscribed instruments: {len(self.instruments)}")
            logger.debug(f"Top 5: {self.instruments[:5]}")

            # Fetch initial orderbook snapshot via REST API
            # This ensures we have baseline data, since WebSocket may only send updates
            logger.info("Fetching initial orderbook snapshot via REST API...")
            snapshot_fetcher = OrderbookSnapshotFetcher(
                database_url=self.database_url,
                rest_api_url="https://www.deribit.com/api/v2"
            )
            snapshot_stats = await snapshot_fetcher.fetch_and_populate(self.instruments, save_full_depth=True)
            logger.info(
                f"Initial snapshot complete: {snapshot_stats['quotes_populated']} quotes, "
                f"{snapshot_stats['depth_snapshots']} depth snapshots, "
                f"{snapshot_stats['instruments_with_data']} instruments with data"
            )

            # Set running flag
            self.running = True

            # Start tasks
            tasks = [
                asyncio.create_task(self._websocket_loop()),
                asyncio.create_task(self._flush_loop()),
                asyncio.create_task(self._heartbeat_monitor()),
                asyncio.create_task(self._stats_logger()),
                asyncio.create_task(self._periodic_snapshot_loop())  # NEW: Periodic REST snapshots
            ]

            # Wait for all tasks
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Fatal error in collector: {e}", exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the collector gracefully."""
        logger.info("Stopping WebSocket tick collector...")
        self.running = False

        # Flush remaining buffers
        logger.info("Flushing remaining buffers...")
        await self._flush_buffers()

        # Close WebSocket
        if self.ws:
            await self.ws.close()

        # Close database connection
        await self.writer.close()

        logger.info("WebSocket tick collector stopped")

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
                    logger.info("WebSocket connected successfully")

                    # Reset reconnect delay on successful connection
                    self.reconnect_delay = 1

                    # Subscribe to instruments
                    await self._subscribe_to_instruments()

                    # Process messages
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
        """Subscribe to quote and trade channels for all instruments."""
        channels = []

        for instrument in self.instruments:
            # Subscribe to order book (quote ticks)
            channels.append(f"book.{instrument}.100ms")
            # Subscribe to trades
            channels.append(f"trades.{instrument}.100ms")

        # Send subscription message
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

        # Wait for subscription confirmation
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

                # Handle different message types
                if 'params' in data:
                    channel = data['params'].get('channel', '')
                    tick_data = data['params'].get('data', {})

                    # Update heartbeat
                    self.last_tick_time = datetime.now()

                    # Route to appropriate handler
                    if channel.startswith('book.'):
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
        """
        Handle quote tick from book.{instrument}.100ms channel.

        Args:
            data: Quote data from WebSocket
        """
        try:
            # Extract quote data (best bid/ask for Level 1)
            quote = {
                'timestamp': datetime.fromtimestamp(data['timestamp'] / 1000),
                'instrument_name': data['instrument_name'],
                'best_bid_price': data.get('best_bid_price'),
                'best_bid_amount': data.get('best_bid_amount'),
                'best_ask_price': data.get('best_ask_price'),
                'best_ask_amount': data.get('best_ask_amount'),
                'underlying_price': data.get('underlying_price'),
                'mark_price': data.get('mark_price')
            }

            # Add to buffer
            self.buffer.add_quote(quote)
            self.stats['quotes_received'] += 1

            # NOTE: WebSocket orderbook sends delta updates in format:
            # [["action", price, amount], ...] where action is "new"/"change"/"delete"
            # This is different from REST API which sends [[price, amount], ...]
            #
            # Instead of trying to reconstruct orderbook from deltas (complex),
            # we rely on periodic REST API snapshots (every 5 minutes) for full depth.
            # This provides complete, accurate orderbook data for backtesting.

        except Exception as e:
            logger.error(f"Failed to process quote tick: {e}")
            self.stats['errors'] += 1

    async def _handle_trade_tick(self, data: Dict):
        """
        Handle trade tick from trades.{instrument}.100ms channel.

        Args:
            data: Trade data from WebSocket (may contain multiple trades)
        """
        try:
            # Deribit sends trades as a list
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

                # Add to buffer
                self.buffer.add_trade(trade)
                self.stats['trades_received'] += 1

        except Exception as e:
            logger.error(f"Failed to process trade tick: {e}")
            self.stats['errors'] += 1

    async def _flush_loop(self):
        """Periodic buffer flush loop."""
        while self.running:
            try:
                # Wait for flush interval or buffer threshold
                await asyncio.sleep(self.flush_interval_sec)

                # Check if buffer should be flushed
                if self.buffer.should_flush() or self.buffer.get_quote_count() > 0 or self.buffer.get_trade_count() > 0:
                    await self._flush_buffers()

            except Exception as e:
                logger.error(f"Error in flush loop: {e}", exc_info=True)

    async def _flush_buffers(self):
        """Flush buffers to database."""
        try:
            # Get and clear buffers (atomic operation)
            quotes, trades, depth = self.buffer.get_and_clear()

            # Write to database
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
                            f"No ticks received for {time_since_last_tick:.0f}s "
                            f"(timeout: {self.heartbeat_timeout_sec}s)"
                        )

            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}", exc_info=True)

    async def _stats_logger(self):
        """Log statistics every 60 seconds."""
        while self.running:
            try:
                await asyncio.sleep(60)

                # Get buffer stats
                buffer_stats = self.buffer.get_stats_summary()

                # Get writer stats
                writer_stats = self.writer.get_stats()

                logger.info(
                    f"STATS | Ticks: {self.stats['ticks_processed']} "
                    f"| Quotes: {self.stats['quotes_received']} "
                    f"| Trades: {self.stats['trades_received']} "
                    f"| Depth: {self.stats.get('depth_received', 0)} "
                    f"| Errors: {self.stats['errors']} "
                    f"| Buffer: Q={buffer_stats['quotes']['utilization_pct']:.1f}% "
                    f"T={buffer_stats['trades']['utilization_pct']:.1f}% "
                    f"D={buffer_stats['depth']['utilization_pct']:.1f}% "
                    f"| DB Writes: Q={writer_stats['quotes_written']} "
                    f"T={writer_stats['trades_written']}"
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

        # Exponential backoff (cap at max_reconnect_delay)
        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def _periodic_snapshot_loop(self):
        """
        Fetch periodic REST API snapshots to ensure complete pricing data.

        This solves the WebSocket delta update issue by periodically fetching
        full orderbook data via REST API. Essential for backtesting data quality.

        Interval: Every 5 minutes (configurable via SNAPSHOT_INTERVAL_SEC env var)
        """
        # Get snapshot interval from environment (default: 5 minutes)
        snapshot_interval_sec = int(os.getenv('SNAPSHOT_INTERVAL_SEC', 300))

        logger.info(f"Periodic snapshot loop started (interval: {snapshot_interval_sec}s)")

        while self.running:
            try:
                # Wait for the configured interval
                await asyncio.sleep(snapshot_interval_sec)

                if not self.running:
                    break

                logger.info("Fetching periodic REST API snapshot...")

                # Create snapshot fetcher
                snapshot_fetcher = OrderbookSnapshotFetcher(
                    database_url=self.database_url,
                    rest_api_url="https://www.deribit.com/api/v2"
                )

                # Fetch and populate (with full depth enabled)
                snapshot_stats = await snapshot_fetcher.fetch_and_populate(self.instruments, save_full_depth=True)

                logger.info(
                    f"Periodic snapshot complete: {snapshot_stats['quotes_populated']} quotes, "
                    f"{snapshot_stats['instruments_with_data']} instruments with data, "
                    f"{snapshot_stats['instruments_without_data']} inactive"
                )

            except Exception as e:
                logger.error(f"Error in periodic snapshot loop: {e}", exc_info=True)
                # Continue running even if snapshot fails


async def main():
    """Main entry point for WebSocket tick collector."""
    # Load configuration from environment
    WS_URL = os.getenv('DERIBIT_WS_URL', 'wss://www.deribit.com/ws/api/v2')
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')
    BUFFER_SIZE_QUOTES = int(os.getenv('BUFFER_SIZE_QUOTES', 200000))
    BUFFER_SIZE_TRADES = int(os.getenv('BUFFER_SIZE_TRADES', 100000))
    FLUSH_INTERVAL_SEC = int(os.getenv('FLUSH_INTERVAL_SEC', 3))
    TOP_N_INSTRUMENTS = int(os.getenv('TOP_N_INSTRUMENTS', 50))

    # Create collector
    collector = WebSocketTickCollector(
        ws_url=WS_URL,
        database_url=DATABASE_URL,
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
