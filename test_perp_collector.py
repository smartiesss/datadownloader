"""
Quick test of perpetual collector - 2 minute run
"""
import asyncio
import os
import sys
from datetime import datetime

# Set environment
os.environ['DATABASE_URL'] = 'postgresql://postgres@localhost:5432/crypto_data'
os.environ['LOG_LEVEL'] = 'INFO'
os.environ['BUFFER_SIZE_QUOTES'] = '10000'
os.environ['BUFFER_SIZE_TRADES'] = '5000'
os.environ['FLUSH_INTERVAL_SEC'] = '3'
os.environ['SNAPSHOT_INTERVAL_SEC'] = '60'  # 1 minute for testing

async def test_collector():
    """Run collector for 2 minutes"""
    from scripts.ws_perp_collector import WebSocketPerpetualCollector

    print("=" * 80)
    print("TESTING PERPETUAL COLLECTOR")
    print("=" * 80)
    print(f"Start time: {datetime.now()}")
    print()

    collector = WebSocketPerpetualCollector(
        ws_url='wss://www.deribit.com/ws/api/v2',
        database_url='postgresql://postgres@localhost:5432/crypto_data',
        buffer_size_quotes=10000,
        buffer_size_trades=5000,
        flush_interval_sec=3
    )

    # Start collector
    task = asyncio.create_task(collector.start())

    # Run for 2 minutes
    print("Running for 2 minutes...")
    print()
    await asyncio.sleep(120)

    # Stop collector
    print()
    print("=" * 80)
    print("STOPPING COLLECTOR")
    print("=" * 80)
    await collector.stop()

    # Cancel the task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print(f"End time: {datetime.now()}")
    print()
    print("Now checking database for results...")
    print()

async def check_database():
    """Check database for collected data"""
    import asyncpg

    conn = await asyncpg.connect('postgresql://postgres@localhost:5432/crypto_data')

    # Check quotes
    quotes = await conn.fetch("""
        SELECT
            instrument,
            COUNT(*) as count,
            COUNT(best_bid_price) as bid_count,
            COUNT(best_ask_price) as ask_count,
            COUNT(mark_price) as mark_count,
            COUNT(index_price) as index_count,
            COUNT(funding_rate) as funding_count,
            MIN(timestamp) as first,
            MAX(timestamp) as last
        FROM perpetuals_quotes
        WHERE timestamp > NOW() - INTERVAL '3 minutes'
        GROUP BY instrument
        ORDER BY instrument
    """)

    print("QUOTES DATA:")
    print("-" * 80)
    for row in quotes:
        print(f"Instrument: {row['instrument']}")
        print(f"  Total rows: {row['count']}")
        print(f"  Bid/Ask populated: {row['bid_count']}/{row['ask_count']}")
        print(f"  Mark/Index/Funding: {row['mark_count']}/{row['index_count']}/{row['funding_count']}")
        print(f"  Time range: {row['first']} to {row['last']}")
        print()

    # Check trades
    trades = await conn.fetch("""
        SELECT
            instrument,
            COUNT(*) as count,
            MIN(timestamp) as first,
            MAX(timestamp) as last
        FROM perpetuals_trades
        WHERE timestamp > NOW() - INTERVAL '3 minutes'
        GROUP BY instrument
        ORDER BY instrument
    """)

    print("TRADES DATA:")
    print("-" * 80)
    for row in trades:
        print(f"Instrument: {row['instrument']}")
        print(f"  Total trades: {row['count']}")
        print(f"  Time range: {row['first']} to {row['last']}")
        print()

    # Show sample quote data
    sample = await conn.fetch("""
        SELECT
            instrument,
            ROUND(best_bid_price::numeric, 2) as bid,
            ROUND(best_ask_price::numeric, 2) as ask,
            ROUND(mark_price::numeric, 2) as mark,
            ROUND(index_price::numeric, 2) as index,
            ROUND(funding_rate::numeric, 8) as funding,
            timestamp
        FROM perpetuals_quotes
        WHERE timestamp > NOW() - INTERVAL '30 seconds'
        ORDER BY timestamp DESC
        LIMIT 5
    """)

    print("SAMPLE RECENT QUOTES:")
    print("-" * 80)
    for row in sample:
        print(f"{row['timestamp']} | {row['instrument']:15} | "
              f"Bid: {row['bid']:8} | Ask: {row['ask']:8} | "
              f"Mark: {row['mark']} | Index: {row['index']} | Funding: {row['funding']}")

    await conn.close()

async def main():
    try:
        await test_collector()
        await check_database()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
