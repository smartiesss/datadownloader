"""
Example: Access Tick Data from External Python Program
Demonstrates different ways to query the database
"""

import asyncpg
import asyncio
from datetime import datetime, timedelta


async def example_1_basic_query():
    """Example 1: Basic connection and query"""
    
    # Connection parameters
    conn = await asyncpg.connect(
        host='localhost',      # or your NAS IP (e.g., '192.168.1.100')
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password_here'  # Change this!
    )
    
    # Query last 100 ticks
    rows = await conn.fetch("""
        SELECT timestamp, instrument, best_bid_price, best_ask_price, underlying_price
        FROM eth_option_quotes
        ORDER BY timestamp DESC
        LIMIT 100
    """)
    
    print(f"Found {len(rows)} ticks")
    for row in rows[:5]:
        print(f"{row['timestamp']} | {row['instrument']} | Bid: {row['best_bid_price']} | Ask: {row['best_ask_price']}")
    
    await conn.close()


async def example_2_time_range_query():
    """Example 2: Query specific time range"""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password_here'
    )
    
    # Get last hour of data
    one_hour_ago = datetime.now() - timedelta(hours=1)
    
    rows = await conn.fetch("""
        SELECT 
            instrument,
            COUNT(*) as tick_count,
            AVG(best_bid_price) as avg_bid,
            AVG(best_ask_price) as avg_ask,
            MIN(timestamp) as first_tick,
            MAX(timestamp) as last_tick
        FROM eth_option_quotes
        WHERE timestamp >= $1
        GROUP BY instrument
        ORDER BY tick_count DESC
    """, one_hour_ago)
    
    print(f"\nTick statistics (last hour):")
    for row in rows[:10]:
        print(f"{row['instrument']}: {row['tick_count']} ticks | Avg spread: {float(row['avg_ask']) - float(row['avg_bid']):.4f}")
    
    await conn.close()


async def example_3_option_chain():
    """Example 3: Get option chain for specific expiry"""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password_here'
    )
    
    # Get all options expiring on a specific date
    expiry_date = '29NOV24'  # Change to your target expiry
    
    rows = await conn.fetch("""
        SELECT DISTINCT
            instrument,
            best_bid_price,
            best_ask_price,
            underlying_price,
            mark_price
        FROM eth_option_quotes
        WHERE instrument LIKE $1
        AND timestamp >= NOW() - INTERVAL '5 minutes'
        ORDER BY instrument
    """, f'ETH-{expiry_date}%')
    
    print(f"\nOption chain for {expiry_date}:")
    for row in rows[:20]:
        print(f"{row['instrument']}: Mark={row['mark_price']} | Bid={row['best_bid_price']} | Ask={row['best_ask_price']}")
    
    await conn.close()


async def example_4_connection_pool():
    """Example 4: Using connection pool (recommended for production)"""
    
    # Create connection pool (reusable connections)
    pool = await asyncpg.create_pool(
        host='localhost',
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password_here',
        min_size=2,
        max_size=10
    )
    
    # Use pool for query
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM eth_option_quotes")
        print(f"\nTotal ticks in database: {count:,}")
        
        latest = await conn.fetchrow("""
            SELECT timestamp, instrument, best_bid_price, best_ask_price
            FROM eth_option_quotes
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        print(f"Latest tick: {latest['timestamp']} | {latest['instrument']}")
    
    await pool.close()


async def example_5_pandas_export():
    """Example 5: Export to Pandas DataFrame for analysis"""
    
    import pandas as pd
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password_here'
    )
    
    # Get data for specific instrument
    rows = await conn.fetch("""
        SELECT timestamp, best_bid_price, best_ask_price, underlying_price, mark_price
        FROM eth_option_quotes
        WHERE instrument = 'ETH-29NOV24-3200-C'
        AND timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY timestamp
    """)
    
    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=['timestamp', 'best_bid_price', 'best_ask_price', 'underlying_price', 'mark_price'])
    
    print(f"\nDataFrame shape: {df.shape}")
    print(df.head())
    
    # Can now do pandas analysis
    print(f"\nStatistics:")
    print(df[['best_bid_price', 'best_ask_price', 'mark_price']].describe())
    
    await conn.close()


if __name__ == "__main__":
    # Run examples
    print("=" * 60)
    print("Example 1: Basic Query")
    print("=" * 60)
    asyncio.run(example_1_basic_query())
    
    print("\n" + "=" * 60)
    print("Example 2: Time Range Query")
    print("=" * 60)
    asyncio.run(example_2_time_range_query())
    
    print("\n" + "=" * 60)
    print("Example 3: Option Chain")
    print("=" * 60)
    asyncio.run(example_3_option_chain())
    
    print("\n" + "=" * 60)
    print("Example 4: Connection Pool")
    print("=" * 60)
    asyncio.run(example_4_connection_pool())
    
    print("\n" + "=" * 60)
    print("Example 5: Pandas Export")
    print("=" * 60)
    asyncio.run(example_5_pandas_export())
