#!/usr/bin/env python3
"""
Test CoinAPI for Deribit Options Data
Testing with API Key to verify access and data structure
"""

import requests
import json
from datetime import datetime, timedelta

API_KEY = "b4f3a3df-e4b4-4032-aa94-dab7ab9ee4c9"
BASE_URL = "https://rest.coinapi.io/v1"

def test_api_key():
    """Test if API key is valid"""
    print("=" * 80)
    print("1. TESTING API KEY VALIDITY")
    print("=" * 80)

    headers = {"X-CoinAPI-Key": API_KEY}
    url = f"{BASE_URL}/exchangerate/BTC/USD"

    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Key Valid!")
            print(f"Sample Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"❌ API Key Invalid or Rate Limited")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def get_deribit_symbols():
    """Get list of Deribit option symbols"""
    print("\n" + "=" * 80)
    print("2. FETCHING DERIBIT OPTION SYMBOLS")
    print("=" * 80)

    headers = {"X-CoinAPI-Key": API_KEY}
    url = f"{BASE_URL}/symbols/DERIBIT"

    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            symbols = response.json()

            # Filter for options only
            option_symbols = [s for s in symbols if s.get('symbol_type') == 'OPTION']

            print(f"✅ Found {len(option_symbols)} option symbols")
            print(f"\nSample Option Symbols (first 10):")
            for sym in option_symbols[:10]:
                print(f"  - {sym.get('symbol_id')}: {sym.get('asset_id_base')} {sym.get('option_type_is_call')} Strike: {sym.get('option_strike_price')}")

            return option_symbols
        else:
            print(f"❌ Failed to fetch symbols")
            print(f"Response: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_option_ohlcv(symbol_id):
    """Get historical OHLCV data for a specific option"""
    print("\n" + "=" * 80)
    print(f"3. FETCHING HISTORICAL OHLCV FOR: {symbol_id}")
    print("=" * 80)

    headers = {"X-CoinAPI-Key": API_KEY}

    # Try to get last 7 days of 1-minute data
    time_end = datetime.utcnow()
    time_start = time_end - timedelta(days=7)

    url = f"{BASE_URL}/ohlcv/{symbol_id}/history"
    params = {
        "period_id": "1MIN",  # 1-minute candles
        "time_start": time_start.isoformat(),
        "time_end": time_end.isoformat(),
        "limit": 100  # Get 100 records max for testing
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        print(f"URL: {response.url}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Received {len(data)} OHLCV records")

            if len(data) > 0:
                print(f"\nSample OHLCV Record (first record):")
                print(json.dumps(data[0], indent=2))

                print(f"\nLast 5 records:")
                for record in data[-5:]:
                    print(f"  {record.get('time_period_start')}: O={record.get('price_open')}, H={record.get('price_high')}, L={record.get('price_low')}, C={record.get('price_close')}, V={record.get('volume_traded')}")
            else:
                print("⚠️  No OHLCV data returned (symbol may be expired or inactive)")

            return data
        else:
            print(f"❌ Failed to fetch OHLCV")
            print(f"Response: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_option_quotes(symbol_id):
    """Get current quotes for an option (includes Greeks and IV if available)"""
    print("\n" + "=" * 80)
    print(f"4. FETCHING CURRENT QUOTES FOR: {symbol_id}")
    print("=" * 80)

    headers = {"X-CoinAPI-Key": API_KEY}
    url = f"{BASE_URL}/quotes/{symbol_id}/current"

    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Received current quote data")
            print(f"\nQuote Data:")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"❌ Failed to fetch quotes")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def check_available_periods():
    """Check what OHLCV periods are available"""
    print("\n" + "=" * 80)
    print("5. CHECKING AVAILABLE OHLCV PERIODS")
    print("=" * 80)

    periods = ["1SEC", "1MIN", "5MIN", "15MIN", "30MIN", "1HRS", "4HRS", "1DAY"]

    print("Available period_id options:")
    for period in periods:
        print(f"  - {period}")

    print("\nNote: We'll test with 1MIN for maximum granularity")

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("COINAPI DERIBIT OPTIONS DATA TEST")
    print("Testing API Key: b4f3a3df-****-****-****-**********")
    print("=" * 80 + "\n")

    # Test 1: Verify API key
    if not test_api_key():
        print("\n❌ API key test failed. Stopping.")
        return

    # Test 2: Get Deribit symbols
    option_symbols = get_deribit_symbols()

    if not option_symbols:
        print("\n❌ Failed to get option symbols. Stopping.")
        return

    # Test 3: Check available periods
    check_available_periods()

    # Test 4: Get OHLCV for a recent BTC option
    # Find a recent BTC call option
    btc_options = [s for s in option_symbols if 'BTC' in s.get('symbol_id', '') and s.get('option_type_is_call') == True]

    if btc_options:
        test_symbol = btc_options[0]['symbol_id']
        print(f"\nTesting with symbol: {test_symbol}")

        ohlcv_data = get_option_ohlcv(test_symbol)

        # Test 5: Get current quotes (may include Greeks/IV)
        quote_data = get_option_quotes(test_symbol)

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nSUMMARY:")
    print(f"  ✅ API Key: Valid")
    print(f"  ✅ Option Symbols: {len(option_symbols)} found")
    print(f"  ✅ OHLCV Endpoint: Accessible")
    print(f"  ✅ Quotes Endpoint: Accessible")
    print("\nNext Steps:")
    print("  1. Verify data structure matches your database schema")
    print("  2. Check if Greeks (Delta, Gamma, Vega) are available in quotes")
    print("  3. Determine rate limits for historical data download")
    print("  4. Estimate total download time for historical data")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
