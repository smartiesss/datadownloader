"""
Test Full Orderbook Depth Storage

This script tests the full orderbook depth saving functionality and measures storage requirements.
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
from scripts.instrument_fetcher import InstrumentFetcher
from scripts.orderbook_snapshot import OrderbookSnapshotFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    load_dotenv()

    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')

    print("=" * 80)
    print("FULL ORDERBOOK DEPTH STORAGE TEST")
    print("=" * 80)
    print()

    # Fetch top 50 instruments
    print("📊 Fetching top 50 ETH options...")
    instrument_fetcher = InstrumentFetcher()
    instruments = await instrument_fetcher.get_top_n_eth_options(n=50)
    print(f"✅ Found {len(instruments)} instruments")
    print()

    # Test 1: Fetch WITH full depth
    print("=" * 80)
    print("TEST 1: Fetching orderbook WITH full depth (20 levels)")
    print("=" * 80)
    snapshot_fetcher = OrderbookSnapshotFetcher(DATABASE_URL)
    stats = await snapshot_fetcher.fetch_and_populate(instruments, save_full_depth=True)

    print()
    print(f"✅ Fetch complete:")
    print(f"   - Instruments fetched: {stats['instruments_fetched']}")
    print(f"   - Quotes populated: {stats['quotes_populated']}")
    print(f"   - Depth snapshots: {stats['depth_snapshots']}")
    print(f"   - Instruments with data: {stats['instruments_with_data']}")
    print(f"   - Instruments without data: {stats['instruments_without_data']}")
    print(f"   - Errors: {stats['errors']}")
    print()

    # Measure storage
    print("=" * 80)
    print("STORAGE ANALYSIS")
    print("=" * 80)
    print()

    # Import psycopg2 for direct query
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get table sizes
    cur.execute("""
        SELECT
            schemaname,
            tablename AS table_name,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
            pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
        FROM pg_tables
        WHERE tablename IN ('eth_option_quotes', 'eth_option_orderbook_depth')
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
    """)

    print("📊 Table Sizes:")
    print("-" * 80)
    print(f"{'Table Name':<35} {'Total Size':<15}")
    print("-" * 80)

    total_bytes = 0
    for row in cur.fetchall():
        schema, table_name, total_size, size_bytes = row
        print(f"{table_name:<35} {total_size:<15}")
        total_bytes += size_bytes

    print("-" * 80)
    print(f"{'TOTAL':<35} {pg_size_pretty(total_bytes):<15}")
    print()

    # Get average row size for depth table
    cur.execute("""
        SELECT
            COUNT(*) as rows,
            pg_total_relation_size('eth_option_orderbook_depth') as total_bytes,
            CASE
                WHEN COUNT(*) > 0
                THEN pg_total_relation_size('eth_option_orderbook_depth') / COUNT(*)
                ELSE 0
            END as avg_row_bytes
        FROM eth_option_orderbook_depth;
    """)

    row_count, total_bytes, avg_row_bytes = cur.fetchone()

    print("📈 Depth Table Statistics:")
    print("-" * 80)
    print(f"   Total rows: {row_count}")
    print(f"   Total size: {pg_size_pretty(total_bytes)}")
    print(f"   Avg row size: {avg_row_bytes} bytes ({avg_row_bytes / 1024:.2f} KB)")
    print()

    # Sample depth data
    cur.execute("""
        SELECT
            instrument,
            timestamp,
            jsonb_array_length(bids) as num_bids,
            jsonb_array_length(asks) as num_asks,
            mark_price,
            underlying_price
        FROM eth_option_orderbook_depth
        ORDER BY timestamp DESC
        LIMIT 5;
    """)

    print("📋 Sample Depth Data:")
    print("-" * 80)
    print(f"{'Instrument':<20} {'Bids':<6} {'Asks':<6} {'Mark':<12} {'Underlying':<12}")
    print("-" * 80)
    for row in cur.fetchall():
        instrument, timestamp, num_bids, num_asks, mark_price, underlying_price = row
        print(f"{instrument:<20} {num_bids:<6} {num_asks:<6} {mark_price:<12.4f} {underlying_price:<12.2f}")
    print()

    # Storage projections
    print("=" * 80)
    print("STORAGE PROJECTIONS")
    print("=" * 80)
    print()

    if row_count > 0:
        # Assume periodic snapshots every 5 minutes (12 per hour)
        snapshots_per_hour = 12
        snapshots_per_day = snapshots_per_hour * 24
        bytes_per_day = avg_row_bytes * stats['instruments_with_data'] * snapshots_per_day

        print(f"Assumptions:")
        print(f"   - Instruments tracked: {stats['instruments_with_data']}")
        print(f"   - Snapshot interval: 5 minutes (12/hour)")
        print(f"   - Average row size: {avg_row_bytes} bytes")
        print()
        print(f"Daily Storage (Full Depth):")
        print(f"   - Depth snapshots/day: {stats['instruments_with_data'] * snapshots_per_day:,}")
        print(f"   - Storage/day: {pg_size_pretty(bytes_per_day)}")
        print()
        print(f"Long-term Projections:")
        print(f"   - 1 month: {pg_size_pretty(bytes_per_day * 30)}")
        print(f"   - 1 year: {pg_size_pretty(bytes_per_day * 365)}")
        print(f"   - 5 years: {pg_size_pretty(bytes_per_day * 365 * 5)}")
        print()

        # Compare with quotes table
        cur.execute("SELECT pg_total_relation_size('eth_option_quotes');")
        quotes_size = cur.fetchone()[0]

        print(f"Comparison:")
        print(f"   - Quote snapshots (Level 1): {pg_size_pretty(quotes_size)}")
        print(f"   - Depth snapshots (Level 20): {pg_size_pretty(total_bytes)}")
        print(f"   - Size increase: {(total_bytes / quotes_size * 100):.1f}% larger")

    cur.close()
    conn.close()

    print()
    print("=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)


def pg_size_pretty(bytes):
    """Convert bytes to human-readable format."""
    if bytes < 1024:
        return f"{bytes} bytes"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.2f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes / (1024 * 1024 * 1024):.2f} GB"


if __name__ == "__main__":
    asyncio.run(main())
