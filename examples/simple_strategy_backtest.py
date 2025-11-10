"""
Example: Simple Options Strategy Using Tick Data
Demonstrates how to use tick data for strategy development
"""

import asyncpg
import asyncio
import pandas as pd
from datetime import datetime, timedelta


async def get_tick_data(instrument: str, hours: int = 24):
    """Fetch tick data for analysis"""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password'
    )
    
    rows = await conn.fetch("""
        SELECT 
            timestamp,
            best_bid_price,
            best_ask_price,
            (best_bid_price + best_ask_price) / 2 as mid_price,
            best_ask_price - best_bid_price as spread,
            underlying_price,
            mark_price
        FROM eth_option_quotes
        WHERE instrument = $1
        AND timestamp >= NOW() - INTERVAL '{} hours'
        ORDER BY timestamp
    """.format(hours), instrument)
    
    await conn.close()
    
    # Convert to DataFrame
    df = pd.DataFrame(
        rows,
        columns=['timestamp', 'bid', 'ask', 'mid', 'spread', 'underlying', 'mark']
    )
    
    return df


async def calculate_statistics(instrument: str):
    """Calculate basic statistics for an option"""
    
    df = await get_tick_data(instrument, hours=24)
    
    if len(df) == 0:
        print(f"No data found for {instrument}")
        return
    
    print(f"\n{'='*60}")
    print(f"Statistics for {instrument}")
    print(f"{'='*60}")
    print(f"Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Total ticks: {len(df):,}")
    print(f"\nPrice Statistics:")
    print(f"  Mid Price: ${df['mid'].mean():.4f} (±${df['mid'].std():.4f})")
    print(f"  Spread: ${df['spread'].mean():.4f} (min: ${df['spread'].min():.4f}, max: ${df['spread'].max():.4f})")
    print(f"  Mark Price: ${df['mark'].mean():.4f}")
    print(f"\nUnderlying:")
    print(f"  Average: ${df['underlying'].mean():.2f}")
    print(f"  Range: ${df['underlying'].min():.2f} - ${df['underlying'].max():.2f}")
    
    # Calculate tick frequency
    df['time_diff'] = df['timestamp'].diff()
    avg_interval = df['time_diff'].mean()
    print(f"\nTick Frequency:")
    print(f"  Average interval: {avg_interval}")
    print(f"  Ticks per hour: {3600 / avg_interval.total_seconds():.1f}")


async def find_best_entry(expiry_date: str = '29NOV24'):
    """Find options with best bid-ask spread"""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password'
    )
    
    # Get recent snapshot of all options for this expiry
    rows = await conn.fetch("""
        WITH latest_quotes AS (
            SELECT DISTINCT ON (instrument)
                instrument,
                timestamp,
                best_bid_price,
                best_ask_price,
                (best_bid_price + best_ask_price) / 2 as mid_price,
                best_ask_price - best_bid_price as spread,
                (best_ask_price - best_bid_price) / ((best_bid_price + best_ask_price) / 2) * 100 as spread_pct,
                underlying_price,
                mark_price
            FROM eth_option_quotes
            WHERE instrument LIKE $1
            AND timestamp >= NOW() - INTERVAL '5 minutes'
            ORDER BY instrument, timestamp DESC
        )
        SELECT * FROM latest_quotes
        WHERE spread > 0
        ORDER BY spread_pct ASC
        LIMIT 10
    """, f'ETH-{expiry_date}%')
    
    await conn.close()
    
    print(f"\n{'='*60}")
    print(f"Best 10 Options by Spread % (Expiry: {expiry_date})")
    print(f"{'='*60}")
    print(f"{'Instrument':<25} {'Mid':<10} {'Spread':<10} {'Spread%':<10}")
    print(f"{'-'*60}")
    
    for row in rows:
        print(f"{row['instrument']:<25} ${row['mid_price']:<9.4f} ${row['spread']:<9.4f} {row['spread_pct']:<9.2f}%")


async def detect_arbitrage_opportunities():
    """Detect potential arbitrage opportunities (large spread movements)"""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password'
    )
    
    # Find instruments where spread changed significantly in last hour
    rows = await conn.fetch("""
        WITH spread_stats AS (
            SELECT 
                instrument,
                AVG(best_ask_price - best_bid_price) as avg_spread,
                STDDEV(best_ask_price - best_bid_price) as std_spread,
                COUNT(*) as tick_count
            FROM eth_option_quotes
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            AND timestamp < NOW() - INTERVAL '5 minutes'
            GROUP BY instrument
            HAVING COUNT(*) > 100
        ),
        recent_spreads AS (
            SELECT DISTINCT ON (instrument)
                instrument,
                best_ask_price - best_bid_price as current_spread
            FROM eth_option_quotes
            WHERE timestamp >= NOW() - INTERVAL '1 minute'
            ORDER BY instrument, timestamp DESC
        )
        SELECT 
            s.instrument,
            r.current_spread,
            s.avg_spread,
            s.std_spread,
            (r.current_spread - s.avg_spread) / s.std_spread as z_score
        FROM spread_stats s
        JOIN recent_spreads r ON s.instrument = r.instrument
        WHERE ABS((r.current_spread - s.avg_spread) / s.std_spread) > 2.0
        ORDER BY ABS((r.current_spread - s.avg_spread) / s.std_spread) DESC
        LIMIT 10
    """)
    
    await conn.close()
    
    if len(rows) > 0:
        print(f"\n{'='*60}")
        print(f"Potential Arbitrage Opportunities (|Z-Score| > 2.0)")
        print(f"{'='*60}")
        print(f"{'Instrument':<25} {'Current':<10} {'Avg':<10} {'Z-Score':<10}")
        print(f"{'-'*60}")
        
        for row in rows:
            print(f"{row['instrument']:<25} ${row['current_spread']:<9.4f} ${row['avg_spread']:<9.4f} {row['z_score']:<9.2f}")
    else:
        print("\nNo arbitrage opportunities detected (all spreads within 2 std dev)")


if __name__ == "__main__":
    # Example 1: Calculate statistics for a specific option
    print("\n" + "="*60)
    print("Example 1: Option Statistics")
    print("="*60)
    asyncio.run(calculate_statistics('ETH-29NOV24-3200-C'))
    
    # Example 2: Find best options by spread
    print("\n" + "="*60)
    print("Example 2: Find Best Entry Points")
    print("="*60)
    asyncio.run(find_best_entry('29NOV24'))
    
    # Example 3: Detect arbitrage opportunities
    print("\n" + "="*60)
    print("Example 3: Arbitrage Detection")
    print("="*60)
    asyncio.run(detect_arbitrage_opportunities())
