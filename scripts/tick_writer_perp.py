"""
Perpetual Tick Writer - Async Database Writer for Perpetual Futures
Handles BTC-PERPETUAL and ETH-PERPETUAL tick data

This module writes perpetual futures tick data (quotes, trades, orderbook)
to the perpetuals_* tables (not currency-specific).

Safety Requirements:
- Connection pooling (max 5 connections)
- Batch INSERT (10k rows per transaction)
- Retry logic (3 attempts with exponential backoff)
- Connection cleanup on shutdown
- Performance logging (rows/second)

Usage:
    writer = PerpetualTickWriter(
        database_url="postgresql://user:pass@host:5432/db"
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


class PerpetualTickWriter:
    """
    Async database writer for perpetual futures tick data.

    Features:
    - Connection pooling (asyncpg)
    - Writes to perpetuals_quotes, perpetuals_trades, perpetuals_orderbook_depth
    - Batch INSERT statements (10k rows per transaction)
    - Retry logic with exponential backoff
    - Performance monitoring (rows/second)
    - Graceful connection cleanup
    """

    def __init__(
        self,
        database_url: str,
        pool_min_size: int = 2,
        pool_max_size: int = 5,
        batch_size: int = 10000
    ):
        """
        Initialize database writer for perpetuals.

        Args:
            database_url: PostgreSQL connection URL
            pool_min_size: Minimum number of connections in pool
            pool_max_size: Maximum number of connections in pool
            batch_size: Maximum rows per INSERT transaction
        """
        self.database_url = database_url
        self.pool_min_size = pool_min_size
        self.pool_max_size = pool_max_size
        self.batch_size = batch_size

        # Table names (shared for all perpetuals)
        self.quotes_table = "perpetuals_quotes"
        self.trades_table = "perpetuals_trades"
        self.depth_table = "perpetuals_orderbook_depth"

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
            f"PerpetualTickWriter initialized: "
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
            logger.info("Database connection pool established for perpetuals")

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
            f"Wrote {total_written} perpetual quotes in {duration:.2f}s "
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
            f"Wrote {total_written} perpetual trades in {duration:.2f}s "
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
            f"Wrote {total_written} perpetual depth snapshots in {duration:.2f}s "
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
                    # Prepare batch INSERT
                    # Schema: timestamp, instrument, best_bid_price, best_bid_amount, best_ask_price, best_ask_amount,
                    #         mark_price, index_price, funding_rate, open_interest
                    query = f"""
                        INSERT INTO {self.quotes_table}
                        (timestamp, instrument, best_bid_price, best_bid_amount, best_ask_price, best_ask_amount,
                         mark_price, index_price, funding_rate, open_interest)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (timestamp, instrument) DO UPDATE SET
                            best_bid_price = COALESCE(EXCLUDED.best_bid_price, {self.quotes_table}.best_bid_price),
                            best_bid_amount = COALESCE(EXCLUDED.best_bid_amount, {self.quotes_table}.best_bid_amount),
                            best_ask_price = COALESCE(EXCLUDED.best_ask_price, {self.quotes_table}.best_ask_price),
                            best_ask_amount = COALESCE(EXCLUDED.best_ask_amount, {self.quotes_table}.best_ask_amount),
                            mark_price = COALESCE(EXCLUDED.mark_price, {self.quotes_table}.mark_price),
                            index_price = COALESCE(EXCLUDED.index_price, {self.quotes_table}.index_price),
                            funding_rate = COALESCE(EXCLUDED.funding_rate, {self.quotes_table}.funding_rate),
                            open_interest = COALESCE(EXCLUDED.open_interest, {self.quotes_table}.open_interest)
                    """

                    await conn.executemany(
                        query,
                        [
                            (
                                quote['timestamp'],
                                quote['instrument'],
                                quote.get('best_bid_price'),
                                quote.get('best_bid_amount'),
                                quote.get('best_ask_price'),
                                quote.get('best_ask_amount'),
                                quote.get('mark_price'),
                                quote.get('index_price'),
                                quote.get('funding_rate'),
                                quote.get('open_interest')
                            )
                            for quote in quotes
                        ]
                    )

                    return len(quotes)

            except Exception as e:
                logger.error(f"Batch write failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self._write_stats['failed_writes'] += 1
                    logger.error(f"Failed to write {len(quotes)} perpetual quotes after {max_retries} attempts")
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
                    # Schema: timestamp, trade_id, instrument, price, amount, direction, tick_direction, liquidation
                    query = f"""
                        INSERT INTO {self.trades_table}
                        (timestamp, trade_id, instrument, price, amount, direction, tick_direction, liquidation)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (timestamp, trade_id, instrument) DO NOTHING
                    """

                    await conn.executemany(
                        query,
                        [
                            (
                                trade['timestamp'],
                                trade['trade_id'],
                                trade['instrument'],
                                trade['price'],
                                trade['amount'],
                                trade['direction'],
                                trade.get('tick_direction'),
                                trade.get('liquidation', False)
                            )
                            for trade in trades
                        ]
                    )

                    return len(trades)

            except Exception as e:
                logger.error(f"Batch write failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self._write_stats['failed_writes'] += 1
                    logger.error(f"Failed to write {len(trades)} perpetual trades after {max_retries} attempts")
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
                    # Schema: timestamp, instrument, bids (JSONB), asks (JSONB), mark_price, index_price,
                    #         funding_rate, open_interest, volume_24h
                    query = f"""
                        INSERT INTO {self.depth_table}
                        (timestamp, instrument, bids, asks, mark_price, index_price, funding_rate, open_interest, volume_24h)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
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
                                depth.get('index_price'),
                                depth.get('funding_rate'),
                                depth.get('open_interest'),
                                depth.get('volume_24h')
                            )
                            for depth in depth_snapshots
                        ]
                    )

                    return len(depth_snapshots)

            except Exception as e:
                logger.error(f"Depth batch write failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self._write_stats['failed_writes'] += 1
                    logger.error(f"Failed to write {len(depth_snapshots)} perpetual depth snapshots after {max_retries} attempts")
                    raise

        return 0

    def get_stats(self) -> Dict:
        """
        Get writer statistics.

        Returns:
            Dictionary with write stats
        """
        return {
            'quotes_written': self._write_stats['quotes_written'],
            'trades_written': self._write_stats['trades_written'],
            'depth_written': self._write_stats['depth_written'],
            'total_batches': self._write_stats['total_batches'],
            'failed_writes': self._write_stats['failed_writes'],
            'last_write_time': self._write_stats['last_write_time'].isoformat() if self._write_stats['last_write_time'] else None
        }
