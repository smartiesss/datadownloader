#!/usr/bin/env python3
"""
CryptoDataDownload API Explorer v3
Test OHLCV endpoint with correct auth and parameters
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('CRYPTODATADOWNLOAD_API_KEY')
BASE_URL = "https://api.cryptodatadownload.com/v1"

print("=" * 80)
print("CRYPTODATADOWNLOAD API V3 - OHLCV ENDPOINT TESTING")
print("=" * 80)

# First, get list of available options
print("\n1️⃣  GETTING AVAILABLE OPTIONS LIST")
url = f"{BASE_URL}/data/ohlc/deribit/options/available/"
response = requests.get(url, headers={"Token": API_KEY})

if response.status_code == 200:
    data = response.json()
    available_options = data.get('result', [])

    # Find recent ETH options
    eth_options = [opt for opt in available_options if 'ETH' in opt]
    print(f"   ✅ Found {len(eth_options)} ETH options")

    # Sample a few recent ones
    recent_eth = sorted(eth_options)[-10:]
    print(f"\n   Recent ETH options:")
    for opt in recent_eth:
        print(f"   - {opt}")

    if len(eth_options) > 0:
        test_symbol = recent_eth[0]

        print(f"\n\n2️⃣  TESTING OHLCV DATA FOR: {test_symbol}")

        # Try different URL patterns
        test_urls = [
            f"{BASE_URL}/data/ohlc/deribit/options/",
            f"{BASE_URL}/data/ohlc/deribit/options/{test_symbol}",
            f"{BASE_URL}/data/ohlc/deribit/options/{test_symbol}/",
        ]

        for test_url in test_urls:
            print(f"\n   Testing: {test_url}")

            # Try with Token header
            response = requests.get(test_url, headers={"Token": API_KEY})
            print(f"      Status: {response.status_code}")

            if response.status_code == 200:
                print(f"      ✅ SUCCESS!")
                data = response.json()

                print(f"\n      Response structure:")
                if isinstance(data, dict):
                    print(f"      Keys: {list(data.keys())}")

                    # Check for OHLCV data
                    if 'data' in data:
                        ohlcv_data = data['data']
                        print(f"      Data points: {len(ohlcv_data) if isinstance(ohlcv_data, list) else 'dict'}")

                        if isinstance(ohlcv_data, list) and len(ohlcv_data) > 0:
                            print(f"\n      First data point:")
                            print(json.dumps(ohlcv_data[0], indent=2))

                            print(f"\n      Last data point:")
                            print(json.dumps(ohlcv_data[-1], indent=2))

                            # Check time granularity
                            if len(ohlcv_data) >= 2:
                                t1 = ohlcv_data[0].get('timestamp') or ohlcv_data[0].get('time')
                                t2 = ohlcv_data[1].get('timestamp') or ohlcv_data[1].get('time')
                                print(f"\n      ⏱️  Time between first two candles:")
                                print(f"         Point 1: {t1}")
                                print(f"         Point 2: {t2}")

                print(f"\n      Full response preview:")
                print(json.dumps(data, indent=2)[:1500])

                break
            elif response.status_code == 401:
                print(f"      ❌ 401 Unauthorized")
            elif response.status_code == 404:
                print(f"      ❌ 404 Not Found")
            else:
                print(f"      ❌ {response.status_code}: {response.text[:200]}")

        # Try with query parameters
        print(f"\n\n3️⃣  TESTING WITH QUERY PARAMETERS")

        params_list = [
            {"symbol": test_symbol},
            {"instrument": test_symbol},
            {"option": test_symbol},
        ]

        for params in params_list:
            url = f"{BASE_URL}/data/ohlc/deribit/options/"
            response = requests.get(url, headers={"Token": API_KEY}, params=params)

            print(f"\n   Params: {params}")
            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS!")
                data = response.json()
                print(f"   Response preview: {str(data)[:500]}")
                break
            else:
                print(f"   Response: {response.text[:200]}")

else:
    print(f"   ❌ Failed to get available options: {response.status_code}")

print("\n" + "=" * 80)
print("TESTING COMPLETE")
print("=" * 80)
