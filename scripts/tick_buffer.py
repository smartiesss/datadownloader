"""
Tick Buffer - Thread-Safe In-Memory Tick Buffering
Task: T-001
Acceptance Criteria: AC-001 (Data completeness)

This module provides thread-safe in-memory buffers for quote and trade ticks.
Buffers automatically trigger flush when 80% full and track statistics.

Safety Requirements:
- Thread-safe operations (uses threading.Lock)
- Configurable max sizes (from .env)
- Automatic flush warnings at 80% capacity
- Statistics tracking (ticks received, written, buffer utilization)

Usage:
    buffer = TickBuffer(max_quotes=200000, max_trades=100000)
    buffer.add_quote(quote_data)
    quotes, trades = buffer.get_and_clear()  # Atomic operation
"""

import logging
import threading
from collections import deque
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BufferStats:
    """Statistics for buffer monitoring."""
    ticks_received: int = 0
    ticks_written: int = 0
    flushes_triggered: int = 0
    last_flush_time: Optional[datetime] = None
    peak_utilization_pct: float = 0.0

    def record_flush(self, num_ticks: int, utilization_pct: float):
        """Record a flush operation."""
        self.ticks_written += num_ticks
        self.flushes_triggered += 1
        self.last_flush_time = datetime.now()
        self.peak_utilization_pct = max(self.peak_utilization_pct, utilization_pct)


class TickBuffer:
    """
    Thread-safe in-memory buffer for quote and trade ticks.

    Features:
    - Separate buffers for quotes and trades
    - Thread-safe operations (Lock-protected)
    - Configurable max sizes
    - Automatic 80% full warnings
    - Statistics tracking
    - Atomic get-and-clear operation
    """

    def __init__(
        self,
        max_quotes: int = 200000,
        max_trades: int = 100000,
        max_depth: int = 50000,
        flush_threshold_pct: float = 80.0
    ):
        """
        Initialize tick buffers.

        Args:
            max_quotes: Maximum number of quote ticks to buffer
            max_trades: Maximum number of trade ticks to buffer
            max_depth: Maximum number of depth snapshots to buffer
            flush_threshold_pct: Trigger flush warning at this % capacity (default: 80%)
        """
        self.max_quotes = max_quotes
        self.max_trades = max_trades
        self.max_depth = max_depth
        self.flush_threshold_pct = flush_threshold_pct

        # Thread-safe buffers (deque is NOT thread-safe for append/pop simultaneously)
        self._quotes: deque = deque(maxlen=max_quotes)
        self._trades: deque = deque(maxlen=max_trades)
        self._depth: deque = deque(maxlen=max_depth)
        self._lock = threading.Lock()

        # Statistics tracking
        self.quote_stats = BufferStats()
        self.trade_stats = BufferStats()
        self.depth_stats = BufferStats()

        # Last warning timestamps (to avoid spamming logs)
        self._last_quote_warning: Optional[datetime] = None
        self._last_trade_warning: Optional[datetime] = None
        self._last_depth_warning: Optional[datetime] = None

        logger.info(
            f"TickBuffer initialized: max_quotes={max_quotes}, "
            f"max_trades={max_trades}, max_depth={max_depth}, "
            f"flush_threshold={flush_threshold_pct}%"
        )

    def add_quote(self, quote: Dict):
        """
        Add a quote tick to the buffer.

        Args:
            quote: Quote tick data (timestamp, instrument, bid/ask prices, etc.)

        Thread-safe: Yes
        """
        with self._lock:
            self._quotes.append(quote)
            self.quote_stats.ticks_received += 1

            # Check if buffer is approaching capacity
            utilization = self.get_quote_utilization()
            if utilization >= self.flush_threshold_pct:
                self._warn_buffer_full('quotes', utilization)

    def add_trade(self, trade: Dict):
        """
        Add a trade tick to the buffer.

        Args:
            trade: Trade tick data (timestamp, instrument, price, amount, etc.)

        Thread-safe: Yes
        """
        with self._lock:
            self._trades.append(trade)
            self.trade_stats.ticks_received += 1

            # Check if buffer is approaching capacity
            utilization = self.get_trade_utilization()
            if utilization >= self.flush_threshold_pct:
                self._warn_buffer_full('trades', utilization)

    def add_depth(self, depth: Dict):
        """
        Add a full orderbook depth snapshot to the buffer.

        Args:
            depth: Depth snapshot data (timestamp, instrument, bids[], asks[], etc.)

        Thread-safe: Yes
        """
        with self._lock:
            self._depth.append(depth)
            self.depth_stats.ticks_received += 1

            # Check if buffer is approaching capacity
            utilization = self.get_depth_utilization()
            if utilization >= self.flush_threshold_pct:
                self._warn_buffer_full('depth', utilization)

    def get_and_clear(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Get all buffered ticks and clear buffers (atomic operation).

        Returns:
            Tuple of (quote_ticks, trade_ticks, depth_snapshots)

        Thread-safe: Yes
        """
        with self._lock:
            quotes = list(self._quotes)
            trades = list(self._trades)
            depth = list(self._depth)

            # Record statistics
            quote_utilization = self.get_quote_utilization()
            trade_utilization = self.get_trade_utilization()
            depth_utilization = self.get_depth_utilization()

            self.quote_stats.record_flush(len(quotes), quote_utilization)
            self.trade_stats.record_flush(len(trades), trade_utilization)
            self.depth_stats.record_flush(len(depth), depth_utilization)

            # Clear buffers
            self._quotes.clear()
            self._trades.clear()
            self._depth.clear()

            logger.debug(
                f"Buffer flushed: {len(quotes)} quotes ({quote_utilization:.1f}% full), "
                f"{len(trades)} trades ({trade_utilization:.1f}% full), "
                f"{len(depth)} depth ({depth_utilization:.1f}% full)"
            )

            return quotes, trades, depth

    def get_quote_count(self) -> int:
        """Get current number of quotes in buffer (thread-safe)."""
        with self._lock:
            return len(self._quotes)

    def get_trade_count(self) -> int:
        """Get current number of trades in buffer (thread-safe)."""
        with self._lock:
            return len(self._trades)

    def get_depth_count(self) -> int:
        """Get current number of depth snapshots in buffer (thread-safe)."""
        with self._lock:
            return len(self._depth)

    def get_quote_utilization(self) -> float:
        """Get quote buffer utilization percentage."""
        return (len(self._quotes) / self.max_quotes) * 100 if self.max_quotes > 0 else 0

    def get_trade_utilization(self) -> float:
        """Get trade buffer utilization percentage."""
        return (len(self._trades) / self.max_trades) * 100 if self.max_trades > 0 else 0

    def get_depth_utilization(self) -> float:
        """Get depth buffer utilization percentage."""
        return (len(self._depth) / self.max_depth) * 100 if self.max_depth > 0 else 0

    def get_stats_summary(self) -> Dict:
        """
        Get buffer statistics summary.

        Returns:
            Dictionary with buffer stats and current utilization
        """
        with self._lock:
            return {
                'quotes': {
                    'buffer_count': len(self._quotes),
                    'buffer_capacity': self.max_quotes,
                    'utilization_pct': self.get_quote_utilization(),
                    'total_received': self.quote_stats.ticks_received,
                    'total_written': self.quote_stats.ticks_written,
                    'total_flushes': self.quote_stats.flushes_triggered,
                    'peak_utilization_pct': self.quote_stats.peak_utilization_pct,
                    'last_flush': self.quote_stats.last_flush_time.isoformat() if self.quote_stats.last_flush_time else None
                },
                'trades': {
                    'buffer_count': len(self._trades),
                    'buffer_capacity': self.max_trades,
                    'utilization_pct': self.get_trade_utilization(),
                    'total_received': self.trade_stats.ticks_received,
                    'total_written': self.trade_stats.ticks_written,
                    'total_flushes': self.trade_stats.flushes_triggered,
                    'peak_utilization_pct': self.trade_stats.peak_utilization_pct,
                    'last_flush': self.trade_stats.last_flush_time.isoformat() if self.trade_stats.last_flush_time else None
                },
                'depth': {
                    'buffer_count': len(self._depth),
                    'buffer_capacity': self.max_depth,
                    'utilization_pct': self.get_depth_utilization(),
                    'total_received': self.depth_stats.ticks_received,
                    'total_written': self.depth_stats.ticks_written,
                    'total_flushes': self.depth_stats.flushes_triggered,
                    'peak_utilization_pct': self.depth_stats.peak_utilization_pct,
                    'last_flush': self.depth_stats.last_flush_time.isoformat() if self.depth_stats.last_flush_time else None
                }
            }

    def should_flush(self) -> bool:
        """
        Check if buffer should be flushed (>= 80% full).

        Returns:
            True if any buffer is at or above flush threshold
        """
        return (
            self.get_quote_utilization() >= self.flush_threshold_pct or
            self.get_trade_utilization() >= self.flush_threshold_pct or
            self.get_depth_utilization() >= self.flush_threshold_pct
        )

    def _warn_buffer_full(self, buffer_type: str, utilization: float):
        """
        Log warning when buffer is approaching capacity.

        Args:
            buffer_type: 'quotes', 'trades', or 'depth'
            utilization: Current buffer utilization percentage
        """
        # Rate-limit warnings (max 1 per minute)
        now = datetime.now()
        if buffer_type == 'quotes':
            last_warning = self._last_quote_warning
        elif buffer_type == 'trades':
            last_warning = self._last_trade_warning
        else:
            last_warning = self._last_depth_warning

        if last_warning is None or (now - last_warning).total_seconds() > 60:
            logger.warning(
                f"{buffer_type.capitalize()} buffer {utilization:.1f}% full "
                f"(threshold: {self.flush_threshold_pct}%) - consider flushing to database"
            )

            if buffer_type == 'quotes':
                self._last_quote_warning = now
            elif buffer_type == 'trades':
                self._last_trade_warning = now
            else:
                self._last_depth_warning = now

    def clear_all(self):
        """Clear all buffers without recording stats (for emergency shutdown)."""
        with self._lock:
            quotes_lost = len(self._quotes)
            trades_lost = len(self._trades)
            depth_lost = len(self._depth)

            self._quotes.clear()
            self._trades.clear()
            self._depth.clear()

            if quotes_lost > 0 or trades_lost > 0 or depth_lost > 0:
                logger.warning(
                    f"Emergency buffer clear: {quotes_lost} quotes, {trades_lost} trades, "
                    f"{depth_lost} depth snapshots discarded"
                )


# Example usage and testing
def test_buffer():
    """Test tick buffer functionality."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create small buffer for testing
    buffer = TickBuffer(max_quotes=10, max_trades=5, flush_threshold_pct=80.0)

    # Add some quotes
    for i in range(8):
        buffer.add_quote({
            'timestamp': datetime.now().isoformat(),
            'instrument': f'ETH-TEST-{i}',
            'bid_price': 100.0 + i,
            'ask_price': 101.0 + i
        })

    # Add some trades
    for i in range(3):
        buffer.add_trade({
            'timestamp': datetime.now().isoformat(),
            'instrument': f'ETH-TEST-{i}',
            'price': 100.5 + i,
            'amount': 10.0
        })

    # Check utilization
    print(f"\nQuote buffer: {buffer.get_quote_count()} / {buffer.max_quotes} ({buffer.get_quote_utilization():.1f}%)")
    print(f"Trade buffer: {buffer.get_trade_count()} / {buffer.max_trades} ({buffer.get_trade_utilization():.1f}%)")

    # Get and clear
    quotes, trades = buffer.get_and_clear()
    print(f"\nFlushed: {len(quotes)} quotes, {len(trades)} trades")

    # Check stats
    stats = buffer.get_stats_summary()
    print(f"\nStats: {stats}")


if __name__ == "__main__":
    test_buffer()
