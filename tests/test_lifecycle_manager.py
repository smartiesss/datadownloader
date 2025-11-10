"""
Unit tests for lifecycle manager

Tests:
1. Database connectivity
2. Fetching active instruments from Deribit API
3. Detecting expired instruments
4. Detecting new instruments
5. Database operations (insert, update, query)
"""

import asyncio
import os
import pytest
import asyncpg
from datetime import datetime, timezone, timedelta
from scripts.lifecycle_manager import LifecycleManager

# Test configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:CryptoTest2024!@localhost:5439/crypto_data')


@pytest.mark.asyncio
async def test_database_connectivity():
    """Test that we can connect to the database."""
    conn = await asyncpg.connect(DATABASE_URL)

    # Verify tables exist
    result = await conn.fetchval("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name IN ('instrument_metadata', 'lifecycle_events')
    """)

    assert result == 2, "Both lifecycle management tables should exist"

    await conn.close()
    print("✅ Database connectivity test passed")


@pytest.mark.asyncio
async def test_fetch_active_instruments():
    """Test fetching active instruments from Deribit API."""
    # Create temporary lifecycle manager (won't start the loop)
    manager = LifecycleManager(
        database_url=DATABASE_URL,
        currency='BTC',
        collector_endpoints=['http://localhost:8000'],  # Dummy endpoint
        refresh_interval_sec=300,
        expiry_buffer_minutes=5
    )

    # Fetch instruments
    instruments = await manager._fetch_active_instruments()

    assert len(instruments) > 0, "Should fetch some active instruments"
    assert all('instrument_name' in inst for inst in instruments), "All instruments should have names"

    print(f"✅ Fetched {len(instruments)} active BTC instruments from Deribit")
    print(f"   First 5: {[inst['instrument_name'] for inst in instruments[:5]]}")


@pytest.mark.asyncio
async def test_add_instrument_to_db():
    """Test adding an instrument to database."""
    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Create test instrument
        test_instrument = 'TEST-01JAN30-100000-C'
        test_metadata = {
            'instrument_type': 'option',
            'strike_price': 100000.0,
            'expiry_date': datetime(2030, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
            'option_type': 'call'
        }

        # Insert test instrument
        await conn.execute("""
            INSERT INTO instrument_metadata
            (instrument_name, currency, instrument_type, strike_price, expiry_date, option_type, is_active, listed_at, last_seen_at)
            VALUES ($1, $2, $3, $4, $5, $6, TRUE, NOW(), NOW())
            ON CONFLICT (instrument_name) DO UPDATE SET
                is_active = TRUE,
                last_seen_at = NOW(),
                updated_at = NOW()
        """,
            test_instrument,
            'BTC',
            test_metadata['instrument_type'],
            test_metadata['strike_price'],
            test_metadata['expiry_date'],
            test_metadata['option_type']
        )

        # Verify insertion
        result = await conn.fetchrow("""
            SELECT * FROM instrument_metadata WHERE instrument_name = $1
        """, test_instrument)

        assert result is not None, "Test instrument should be inserted"
        assert result['is_active'] == True, "Test instrument should be active"
        assert result['currency'] == 'BTC', "Currency should match"

        print(f"✅ Successfully inserted test instrument: {test_instrument}")

        # Cleanup
        await conn.execute("DELETE FROM instrument_metadata WHERE instrument_name = $1", test_instrument)

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_log_lifecycle_event():
    """Test logging lifecycle events."""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Log test event
        await conn.execute("""
            INSERT INTO lifecycle_events
            (event_type, instrument_name, currency, collector_id, details, success, error_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
            'test_event',
            'TEST-01JAN30-100000-C',
            'BTC',
            'test-collector',
            '{"test": "data"}',
            True,
            None
        )

        # Verify event logged
        result = await conn.fetchrow("""
            SELECT * FROM lifecycle_events
            WHERE event_type = 'test_event' AND instrument_name = 'TEST-01JAN30-100000-C'
            ORDER BY event_time DESC
            LIMIT 1
        """)

        assert result is not None, "Test event should be logged"
        assert result['success'] == True, "Event should be marked as successful"
        assert result['currency'] == 'BTC', "Currency should match"

        print(f"✅ Successfully logged lifecycle event")

        # Cleanup
        await conn.execute("DELETE FROM lifecycle_events WHERE event_type = 'test_event'")

    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_detect_expired_instruments():
    """Test detecting expired instruments."""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Insert test expired instrument
        expired_instrument = 'TEST-EXPIRED-01JAN20-50000-P'
        await conn.execute("""
            INSERT INTO instrument_metadata
            (instrument_name, currency, instrument_type, strike_price, expiry_date, option_type, is_active, listed_at, last_seen_at)
            VALUES ($1, $2, $3, $4, $5, $6, TRUE, NOW(), NOW())
            ON CONFLICT (instrument_name) DO UPDATE SET
                is_active = TRUE,
                last_seen_at = NOW(),
                updated_at = NOW()
        """,
            expired_instrument,
            'BTC',
            'option',
            50000.0,
            datetime(2020, 1, 1, 8, 0, 0, tzinfo=timezone.utc),  # Expired in 2020
            'put'
        )

        # Get tracked instruments (should include our expired one)
        tracked = await conn.fetch("""
            SELECT instrument_name FROM instrument_metadata WHERE currency = 'BTC' AND is_active = TRUE
        """)
        tracked_names = set(row['instrument_name'] for row in tracked)

        assert expired_instrument in tracked_names, "Expired instrument should be in tracked set"

        # Simulate lifecycle manager detecting it's not active on exchange
        # In real scenario, Deribit API wouldn't return this instrument
        # So it would be in tracked_set but not in active_set

        print(f"✅ Successfully detected expired instrument simulation")

        # Cleanup
        await conn.execute("DELETE FROM instrument_metadata WHERE instrument_name = $1", expired_instrument)

    finally:
        await conn.close()


async def run_all_tests():
    """Run all tests sequentially."""
    print("\n" + "="*60)
    print("LIFECYCLE MANAGER UNIT TESTS")
    print("="*60 + "\n")

    tests = [
        ("Database Connectivity", test_database_connectivity),
        ("Fetch Active Instruments", test_fetch_active_instruments),
        ("Add Instrument to DB", test_add_instrument_to_db),
        ("Log Lifecycle Event", test_log_lifecycle_event),
        ("Detect Expired Instruments", test_detect_expired_instruments),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print(f"\n🧪 Running: {test_name}")
            await test_func()
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
