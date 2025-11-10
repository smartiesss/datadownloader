"""
Tick Writer - Multi-Currency Async Database Writer with Batch INSERT
Supports BTC, ETH, and future currencies

This module handles batch database writes for quote and trade ticks across
multiple currencies. Uses asyncpg for async PostgreSQL operations.

Safety Requirements:
- Connection pooling (max 5 connections)
- Batch INSERT (10k rows per transaction)
- Retry logic (3 attempts with exponential backoff)
- Connection cleanup on shutdown
- Performance logging (rows/second)

Usage:
    writer = MultiCurrencyTickWriter(
        database_url="postgresql://user:pass@host:5432/db",
        currency="BTC"
    )
    await writer.connect()
    await writer.write_quotes(quote_ticks)
    await writer.write_trades(trade_ticks)
    await writer.close()
"""

import asyncpg
import logging
from typing import List, Dict, Optional
from datetime import datetime
import asyncio
import json

logger = logging.getLogger(__name__)


class MultiCurrencyTickWriter:
    """
    Async database writer for quote and trade ticks with multi-currency support.

    Features:
    - Connection pooling (asyncpg)
    - Multi-currency table routing (e.g., eth_option_quotes, btc_option_quotes)
    - Batch INSERT statements (10k rows per transaction)
    - Retry logic with exponential backoff
    - Performance monitoring (rows/second)
    - Graceful connection cleanup
    """

    def __init__(
        self,
        database_url: str,
        currency: str = "ETH",
        pool_min_size: int = 2,
        pool_max_size: int = 5,
        batch_size: int = 10000
    ):
        """
        Initialize database writer.

        Args:
            database_url: PostgreSQL connection URL
            currency: Currency code (BTC, ETH, etc.) for table routing
            pool_min_size: Minimum number of connections in pool
            pool_max_size: Maximum number of connections in pool
            batch_size: Maximum rows per INSERT transaction
        """
        self.database_url = database_url
        self.currency = currency.upper()
        self.pool_min_size = pool_min_size
        self.pool_max_size = pool_max_size
        self.batch_size = batch_size

        # Table names (currency-specific)
        currency_lower = self.currency.lower()
        self.quotes_table = f"{currency_lower}_option_quotes"
        self.trades_table = f"{currency_lower}_option_trades"
        self.depth_table = f"{currency_lower}_option_orderbook_depth"

        self.pool: Optional[asyncpg.Pool] = None
        self._write_stats = {
            'quotes_written': 0,
            'trades_written': 0,
            'depth_written': 0,
            'total_batches': 0,
            'failed_writes': 0,
            'last_write_time': None
        }

        logger.info(
            f"MultiCurrencyTickWriter initialized for {self.currency}: "
            f"pool_size={pool_min_size}-{pool_max_size}, batch_size={batch_size}"
        )

    async def connect(self):
        """
        Establish database connection pool.

        Raises:
            Exception: If connection fails
        """
        try:
            logger.info(f"Connecting to database (pool size: {self.pool_min_size}-{self.pool_max_size})...")
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.pool_min_size,
                max_size=self.pool_max_size,
                command_timeout=60,
                timeout=30
            )
            logger.info(f"Database connection pool established for {self.currency}")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def close(self):
        """Close database connection pool gracefully."""
        if self.pool:
            logger.info("Closing database connection pool...")
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def write_quotes(self, quotes: List[Dict]) -> int:
        """
        Write quote ticks to database in batches.

        Args:
            quotes: List of quote tick dictionaries

        Returns:
            Number of quotes successfully written

        Raises:
            Exception: If write fails after max retries
        """
        if not quotes:
            return 0

        start_time = datetime.now()
        total_written = 0

        # Process in batches
        for i in range(0, len(quotes), self.batch_size):
            batch = quotes[i:i + self.batch_size]
            written = await self._write_quote_batch(batch)
            total_written += written

        # Update stats and log performance
        duration = (datetime.now() - start_time).total_seconds()
        rows_per_sec = total_written / duration if duration > 0 else 0

        self._write_stats['quotes_written'] += total_written
        self._write_stats['total_batches'] += 1
        self._write_stats['last_write_time'] = datetime.now()

        logger.info(
            f"Wrote {total_written} {self.currency} quotes in {duration:.2f}s "
            f"({rows_per_sec:.0f} rows/sec)"
        )

        return total_written

    async def write_trades(self, trades: List[Dict]) -> int:
        """
        Write trade ticks to database in batches.

        Args:
            trades: List of trade tick dictionaries

        Returns:
            Number of trades successfully written

        Raises:
            Exception: If write fails after max retries
        """
        if not trades:
            return 0

        start_time = datetime.now()
        total_written = 0

        # Process in batches
        for i in range(0, len(trades), self.batch_size):
            batch = trades[i:i + self.batch_size]
            written = await self._write_trade_batch(batch)
            total_written += written

        # Update stats and log performance
        duration = (datetime.now() - start_time).total_seconds()
        rows_per_sec = total_written / duration if duration > 0 else 0

        self._write_stats['trades_written'] += total_written
        self._write_stats['total_batches'] += 1
        self._write_stats['last_write_time'] = datetime.now()

        logger.info(
            f"Wrote {total_written} {self.currency} trades in {duration:.2f}s "
            f"({rows_per_sec:.0f} rows/sec)"
        )

        return total_written

    async def write_depth_snapshots(self, depth_snapshots: List[Dict]) -> int:
        """
        Write full orderbook depth snapshots to database in batches.

        Args:
            depth_snapshots: List of depth snapshot dictionaries with JSONB bid/ask levels

        Returns:
            Number of depth snapshots successfully written

        Raises:
            Exception: If write fails after max retries
        """
        if not depth_snapshots:
            return 0

        start_time = datetime.now()
        total_written = 0

        # Process in batches
        for i in range(0, len(depth_snapshots), self.batch_size):
            batch = depth_snapshots[i:i + self.batch_size]
            written = await self._write_depth_batch(batch)
            total_written += written

        # Update stats and log performance
        duration = (datetime.now() - start_time).total_seconds()
        rows_per_sec = total_written / duration if duration > 0 else 0

        self._write_stats['depth_written'] += total_written
        self._write_stats['total_batches'] += 1
        self._write_stats['last_write_time'] = datetime.now()

        logger.info(
            f"Wrote {total_written} {self.currency} depth snapshots in {duration:.2f}s "
            f"({rows_per_sec:.0f} rows/sec)"
        )

        return total_written

    async def _write_quote_batch(self, quotes: List[Dict], max_retries: int = 3) -> int:
        """
        Write a batch of quotes with retry logic.

        Args:
            quotes: Batch of quote dictionaries
            max_retries: Maximum number of retry attempts

        Returns:
            Number of quotes written
        """
        for attempt in range(max_retries):
            try:
                async with self.pool.acquire() as conn:
                    # Prepare batch INSERT with Greeks and IV columns
                    # Schema: timestamp, instrument, bid/ask, underlying, mark, Greeks (delta/gamma/theta/vega/rho), IVs, OI, last_price
                    query = f"""
                        INSERT INTO {self.quotes_table}
                        (timestamp, instrument, best_bid_price, best_bid_amount, best_ask_price, best_ask_amount,
                         underlying_price, mark_price, delta, gamma, theta, vega, rho,
                         implied_volatility, bid_iv, ask_iv, mark_iv, open_interest, last_price)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                        ON CONFLICT (timestamp, instrument) DO UPDATE SET
                            best_bid_price = COALESCE(EXCLUDED.best_bid_price, {self.quotes_table}.best_bid_price),
                            best_bid_amount = COALESCE(EXCLUDED.best_bid_amount, {self.quotes_table}.best_bid_amount),
                            best_ask_price = COALESCE(EXCLUDED.best_ask_price, {self.quotes_table}.best_ask_price),
                            best_ask_amount = COALESCE(EXCLUDED.best_ask_amount, {self.quotes_table}.best_ask_amount),
                            underlying_price = COALESCE(EXCLUDED.underlying_price, {self.quotes_table}.underlying_price),
                            mark_price = COALESCE(EXCLUDED.mark_price, {self.quotes_table}.mark_price),
                            delta = COALESCE(EXCLUDED.delta, {self.quotes_table}.delta),
                            gamma = COALESCE(EXCLUDED.gamma, {self.quotes_table}.gamma),
                            theta = COALESCE(EXCLUDED.theta, {self.quotes_table}.theta),
                            vega = COALESCE(EXCLUDED.vega, {self.quotes_table}.vega),
                            rho = COALESCE(EXCLUDED.rho, {self.quotes_table}.rho),
                            implied_volatility = COALESCE(EXCLUDED.implied_volatility, {self.quotes_table}.implied_volatility),
                            bid_iv = COALESCE(EXCLUDED.bid_iv, {self.quotes_table}.bid_iv),
                            ask_iv = COALESCE(EXCLUDED.ask_iv, {self.quotes_table}.ask_iv),
                            mark_iv = COALESCE(EXCLUDED.mark_iv, {self.quotes_table}.mark_iv),
                            open_interest = COALESCE(EXCLUDED.open_interest, {self.quotes_table}.open_interest),
                            last_price = COALESCE(EXCLUDED.last_price, {self.quotes_table}.last_price)
                    """

                    await conn.executemany(
                        query,
                        [
                            (
                                quote['timestamp'],
                                quote['instrument_name'],
                                quote.get('best_bid_price'),
                                quote.get('best_bid_amount'),
                                quote.get('best_ask_price'),
                                quote.get('best_ask_amount'),
                                quote.get('underlying_price'),
                                quote.get('mark_price'),
                                quote.get('delta'),
                                quote.get('gamma'),
                                quote.get('theta'),
                                quote.get('vega'),
                                quote.get('rho'),
                                quote.get('implied_volatility'),
                                quote.get('bid_iv'),
                                quote.get('ask_iv'),
                                quote.get('mark_iv'),
                                quote.get('open_interest'),
                                quote.get('last_price')
                            )
                            for quote in quotes
                        ]
                    )

                    return len(quotes)

            except Exception as e:
                logger.error(f"Batch write failed for {self.currency} (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self._write_stats['failed_writes'] += 1
                    logger.error(f"Failed to write {len(quotes)} {self.currency} quotes after {max_retries} attempts")
                    raise

        return 0

    async def _write_trade_batch(self, trades: List[Dict], max_retries: int = 3) -> int:
        """
        Write a batch of trades with retry logic.

        Args:
            trades: Batch of trade dictionaries
            max_retries: Maximum number of retry attempts

        Returns:
            Number of trades written
        """
        for attempt in range(max_retries):
            try:
                async with self.pool.acquire() as conn:
                    # Prepare batch INSERT
                    # Schema: timestamp, instrument, trade_id, price, amount, direction, iv, index_price
                    query = f"""
                        INSERT INTO {self.trades_table}
                        (timestamp, instrument, trade_id, price, amount, direction, iv, index_price)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (trade_id, instrument) DO NOTHING
                    """

                    await conn.executemany(
                        query,
                        [
                            (
                                trade['timestamp'],
                                trade['instrument_name'],
                                trade['trade_id'],
                                trade['price'],
                                trade['amount'],
                                trade['direction'],
                                trade.get('iv'),
                                trade.get('index_price')
                            )
                            for trade in trades
                        ]
                    )

                    return len(trades)

            except Exception as e:
                logger.error(f"Batch write failed for {self.currency} (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self._write_stats['failed_writes'] += 1
                    logger.error(f"Failed to write {len(trades)} {self.currency} trades after {max_retries} attempts")
                    raise

        return 0

    async def _write_depth_batch(self, depth_snapshots: List[Dict], max_retries: int = 3) -> int:
        """
        Write a batch of depth snapshots with retry logic.

        Args:
            depth_snapshots: Batch of depth snapshot dictionaries
            max_retries: Maximum number of retry attempts

        Returns:
            Number of depth snapshots written
        """
        for attempt in range(max_retries):
            try:
                async with self.pool.acquire() as conn:
                    # Prepare batch INSERT
                    # Schema: timestamp, instrument, bids (JSONB), asks (JSONB), mark_price, underlying_price, open_interest, volume_24h
                    query = f"""
                        INSERT INTO {self.depth_table}
                        (timestamp, instrument, bids, asks, mark_price, underlying_price, open_interest, volume_24h)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """

                    await conn.executemany(
                        query,
                        [
                            (
                                depth['timestamp'],
                                depth['instrument'],
                                json.dumps(depth.get('bids', [])),  # Convert list to JSONB
                                json.dumps(depth.get('asks', [])),  # Convert list to JSONB
                                depth.get('mark_price'),
                                depth.get('underlying_price'),
                                depth.get('open_interest'),
                                depth.get('volume_24h')
                            )
                            for depth in depth_snapshots
                        ]
                    )

                    return len(depth_snapshots)

            except Exception as e:
                logger.error(f"Depth batch write failed for {self.currency} (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self._write_stats['failed_writes'] += 1
                    logger.error(f"Failed to write {len(depth_snapshots)} {self.currency} depth snapshots after {max_retries} attempts")
                    raise

        return 0

    def get_stats(self) -> Dict:
        """
        Get writer statistics.

        Returns:
            Dictionary with write stats
        """
        return {
            'currency': self.currency,
            'quotes_written': self._write_stats['quotes_written'],
            'trades_written': self._write_stats['trades_written'],
            'depth_written': self._write_stats['depth_written'],
            'total_batches': self._write_stats['total_batches'],
            'failed_writes': self._write_stats['failed_writes'],
            'last_write_time': self._write_stats['last_write_time'].isoformat() if self._write_stats['last_write_time'] else None
        }


# Example usage and testing
async def test_writer():
    """Test multi-currency database writer functionality."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')

    # Test BTC writer
    btc_writer = MultiCurrencyTickWriter(database_url, currency='BTC')

    try:
        # Connect to database
        await btc_writer.connect()

        # Create test quotes
        test_quotes = [
            {
                'timestamp': datetime.now(),
                'instrument_name': 'BTC-TEST-100000-C',
                'best_bid_price': 5000.0,
                'best_bid_amount': 10.0,
                'best_ask_price': 5100.0,
                'best_ask_amount': 15.0,
                'underlying_price': 100000.0,
                'mark_price': 5050.0
            }
            for i in range(10)
        ]

        # Write to database
        await btc_writer.write_quotes(test_quotes)

        # Print stats
        stats = btc_writer.get_stats()
        print(f"\nBTC Writer stats: {stats}")

    finally:
        # Close connection
        await btc_writer.close()


if __name__ == "__main__":
    asyncio.run(test_writer())
