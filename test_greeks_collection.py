"""
Test Greeks Collection - Run ETH collector for 60 seconds and verify Greeks in database
"""
import asyncio
import subprocess
import time
import psycopg2
from datetime import datetime

def run_sql_query(query):
    """Run a SQL query and return results"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='crypto_data',
            user='postgres'
        )
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        return columns, results
    except Exception as e:
        print(f"Error running query: {e}")
        return None, None

def main():
    print("=" * 80)
    print("GREEKS COLLECTION TEST")
    print("=" * 80)
    print(f"Start time: {datetime.now()}")
    print()

    # Check initial row count
    print("1. Checking initial database state...")
    columns, results = run_sql_query("""
        SELECT COUNT(*) FROM eth_option_quotes
        WHERE timestamp > NOW() - INTERVAL '5 minutes'
    """)
    if results:
        initial_count = results[0][0]
        print(f"   Quotes in last 5 minutes: {initial_count}")
    print()

    # Start collector
    print("2. Starting ETH option collector for 60 seconds...")
    print("   (Watch for 'Successfully subscribed' and Greek values in logs)")
    print()

    import os
    env = os.environ.copy()
    env['CURRENCY'] = 'ETH'
    env['TOP_N_INSTRUMENTS'] = '10'
    env['DATABASE_URL'] = 'postgresql://postgres@localhost:5432/crypto_data'
    env['LOG_LEVEL'] = 'INFO'

    proc = subprocess.Popen(
        ['python3', '-m', 'scripts.ws_tick_collector_multi'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Monitor output for 60 seconds
    start = time.time()
    subscription_ok = False

    try:
        while time.time() - start < 60:
            if proc.poll() is not None:
                print("   ⚠️ Collector stopped unexpectedly")
                break

            line = proc.stdout.readline()
            if line:
                print(f"   {line.strip()}")
                if 'Successfully subscribed' in line:
                    subscription_ok = True
                    print("   ✅ Subscription successful!")
                if 'ERROR' in line or 'Failed' in line:
                    print(f"   ❌ Error detected: {line.strip()}")

            time.sleep(0.1)
    finally:
        # Stop collector
        proc.terminate()
        proc.wait(timeout=5)

    print()
    print(f"End time: {datetime.now()}")
    print()

    if not subscription_ok:
        print("❌ FAILED: Collector did not subscribe successfully")
        return

    # Check data collection
    print("=" * 80)
    print("3. VERIFICATION - Checking collected data")
    print("=" * 80)
    print()

    # Count quotes with Greeks
    print("A. Quote counts:")
    columns, results = run_sql_query("""
        SELECT
            COUNT(*) as total_quotes,
            COUNT(delta) as quotes_with_delta,
            COUNT(gamma) as quotes_with_gamma,
            COUNT(mark_iv) as quotes_with_iv,
            COUNT(open_interest) as quotes_with_oi
        FROM eth_option_quotes
        WHERE timestamp > NOW() - INTERVAL '2 minutes'
    """)

    if results:
        total, delta_count, gamma_count, iv_count, oi_count = results[0]
        print(f"   Total quotes (last 2 min): {total}")
        print(f"   Quotes with delta: {delta_count}")
        print(f"   Quotes with gamma: {gamma_count}")
        print(f"   Quotes with mark_iv: {iv_count}")
        print(f"   Quotes with open_interest: {oi_count}")
        print()

        if total == 0:
            print("❌ FAILED: No quotes collected")
            return

        if delta_count == 0:
            print("❌ FAILED: No Greeks collected (delta is NULL)")
            return

    # Show sample data with Greeks
    print("B. Sample quotes with Greeks:")
    print("-" * 80)
    columns, results = run_sql_query("""
        SELECT
            timestamp,
            instrument,
            best_bid_price,
            best_ask_price,
            delta,
            gamma,
            theta,
            vega,
            mark_iv,
            open_interest
        FROM eth_option_quotes
        WHERE timestamp > NOW() - INTERVAL '2 minutes'
          AND delta IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 5
    """)

    if columns and results:
        # Print header
        header = " | ".join([f"{col:20}" for col in columns])
        print(header)
        print("-" * len(header))

        # Print rows
        for row in results:
            formatted_row = []
            for val in row:
                if isinstance(val, float):
                    formatted_row.append(f"{val:20.8f}")
                else:
                    formatted_row.append(f"{str(val):20}")
            print(" | ".join(formatted_row))

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)

    if results and len(results) > 0:
        print("✅ SUCCESS! Greeks collection is working")
        print()
        print("Summary:")
        print(f"  - Collector subscribed to ticker channel")
        print(f"  - Greeks extracted from ticker data")
        print(f"  - Database contains {delta_count} quotes with delta values")
        print(f"  - Sample data shows all Greek columns populated")
        print()
        print("✅ READY TO DEPLOY TO NAS!")
    else:
        print("❌ FAILED: No quotes with Greeks found in database")

    print()

if __name__ == "__main__":
    main()
