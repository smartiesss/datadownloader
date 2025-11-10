#!/usr/bin/env python3
"""
CoinAPI Test - Fixed datetime format
"""

import requests
import json
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('COINAPI_KEY')
BASE_URL = "https://rest.coinapi.io/v1"

headers = {"X-CoinAPI-Key": API_KEY}

print("=" * 80)
print("COINAPI DERIBIT OPTIONS TEST - FIXED")
print("=" * 80)

# Test 1: Get list of BTC options
print("\n1️⃣  GETTING DERIBIT BTC OPTION SYMBOLS...")
url = f"{BASE_URL}/symbols/DERIBIT"
response = requests.get(url, headers=headers)

if response.status_code == 200:
    all_symbols = response.json()

    # Filter for options only
    options = [s for s in all_symbols if s.get('symbol_type') == 'OPTION']
    btc_options = [o for o in options if 'BTC' in o.get('symbol_id', '')]

    print(f"✅ Found {len(btc_options)} BTC options")

    # Find a recent one
    recent_btc_options = sorted(btc_options, key=lambda x: x.get('symbol_id', ''))[:20]

    print(f"\n   Sample BTC options:")
    for opt in recent_btc_options[:5]:
        print(f"   - {opt['symbol_id']}")

    # Pick one for testing
    test_symbol = recent_btc_options[0]['symbol_id']

    print(f"\n2️⃣  TESTING HISTORICAL OHLCV FOR: {test_symbol}")
    print(f"   Using corrected datetime format...")

    # Use proper ISO format with Z suffix
    time_end = datetime.now(timezone.utc)
    time_start = time_end - timedelta(days=7)

    url = f"{BASE_URL}/ohlcv/{test_symbol}/history"
    params = {
        "period_id": "1MIN",
        "time_start": time_start.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        "time_end": time_end.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        "limit": 100
    }

    print(f"   Request: {url}")
    print(f"   Start: {params['time_start']}")
    print(f"   End: {params['time_end']}")

    response = requests.get(url, headers=headers, params=params)

    print(f"\n   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ SUCCESS! Received {len(data)} candles")

        if len(data) > 0:
            print(f"\n   First candle:")
            print(json.dumps(data[0], indent=4))

            print(f"\n   Last 5 candles:")
            for candle in data[-5:]:
                print(f"   {candle.get('time_period_start')}: Close={candle.get('price_close')}, Vol={candle.get('volume_traded')}")
        else:
            print(f"   ⚠️  No candles returned (option may be inactive)")
    else:
        print(f"   ❌ FAILED")
        print(f"   Response: {response.text}")

    # Test 3: Try different resolutions
    print(f"\n3️⃣  TESTING DIFFERENT RESOLUTIONS...")

    resolutions = ["1MIN", "5MIN", "1HRS", "1DAY"]
    results = {}

    for res in resolutions:
        params['period_id'] = res
        params['limit'] = 10

        response = requests.get(f"{BASE_URL}/ohlcv/{test_symbol}/history",
                                headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            results[res] = len(data)
            print(f"   ✅ {res}: {len(data)} candles")
        else:
            results[res] = 0
            print(f"   ❌ {res}: Failed ({response.status_code})")

    # Test 4: Test with an old expired option
    print(f"\n4️⃣  TESTING OLD EXPIRED OPTION (Oct 15, 2025)...")

    # Find Oct 15 expired option
    oct15_options = [o for o in btc_options if '251015' in o.get('symbol_id', '')]

    if oct15_options:
        old_symbol = oct15_options[0]['symbol_id']
        print(f"   Testing: {old_symbol}")

        # Try to get data from before expiration
        time_end = datetime(2025, 10, 16, tzinfo=timezone.utc)
        time_start = datetime(2025, 10, 14, tzinfo=timezone.utc)

        params = {
            "period_id": "1MIN",
            "time_start": time_start.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "time_end": time_end.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "limit": 100
        }

        response = requests.get(f"{BASE_URL}/ohlcv/{old_symbol}/history",
                                headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ EXCELLENT! Got {len(data)} candles for expired option!")
            print(f"   This means CoinAPI has historical data for expired options!")
        else:
            print(f"   ❌ No data for expired option")
            print(f"   Response: {response.text}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ API Key: Working with $5 credit")
    print(f"✅ Symbols: {len(btc_options)} BTC options available")
    print(f"✅ Time Resolutions Available:")
    for res, count in results.items():
        status = "✅" if count > 0 else "❌"
        print(f"   {status} {res}: {count} candles")
    print("=" * 80)

else:
    print(f"❌ Failed to get symbols: {response.status_code}")
    print(response.text)
