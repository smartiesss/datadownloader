#!/usr/bin/env python3
"""
CryptoDataDownload API Explorer
Test available Deribit options data
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('CRYPTODATADOWNLOAD_API_KEY')
BASE_URL = "https://api.cryptodatadownload.com"

# Correct authentication format from documentation
headers = {
    "Authorization": f"TOKEN {API_KEY}",
    "accept": "application/json"
}

print("=" * 80)
print("CRYPTODATADOWNLOAD API EXPLORER - DERIBIT OPTIONS")
print("=" * 80)
print(f"API Key: {API_KEY[:20]}...")
print("=" * 80)

# Test 1: Greeks Summary
print("\n1️⃣  TESTING DERIBIT OPTIONS GREEKS SUMMARY")
url = f"{BASE_URL}/data/summary/deribit/options/greeks/"

response = requests.get(url, headers=headers)
print(f"   Endpoint: {url}")
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"   ✅ SUCCESS!")
    print(f"\n   Response structure:")
    print(json.dumps(data, indent=2)[:1000])  # First 1000 chars

    if isinstance(data, list) and len(data) > 0:
        print(f"\n   Total records: {len(data)}")
        print(f"\n   Sample record:")
        print(json.dumps(data[0], indent=2))
else:
    print(f"   ❌ FAILED: {response.status_code}")
    print(f"   Response: {response.text[:500]}")

# Test 2: Largest Transactions
print("\n\n2️⃣  TESTING LARGEST OPTIONS TRANSACTIONS")
url = f"{BASE_URL}/data/summary/deribit/options/transactions/largest/"

response = requests.get(url, headers=headers)
print(f"   Endpoint: {url}")
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"   ✅ SUCCESS!")

    if isinstance(data, list) and len(data) > 0:
        print(f"\n   Total records: {len(data)}")
        print(f"\n   Sample transaction:")
        print(json.dumps(data[0], indent=2))
    else:
        print(f"\n   Response structure:")
        print(json.dumps(data, indent=2)[:1000])
else:
    print(f"   ❌ FAILED: {response.status_code}")
    print(f"   Response: {response.text[:500]}")

# Test 3: Try to find raw OHLCV or tick data endpoints
print("\n\n3️⃣  EXPLORING OTHER ENDPOINTS")

# Try v1 API endpoints based on documentation examples
test_endpoints = [
    "/v1/",
    "/v1/data",
    "/v1/data/summary",
    "/v1/data/summary/deribit",
    "/v1/data/deribit/options",
    "/v1/options/deribit",
    "/v1/data/options",
]

for endpoint in test_endpoints:
    url = f"{BASE_URL}{endpoint}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print(f"\n   ✅ FOUND: {endpoint}")
        try:
            data = response.json()
            print(f"      Type: JSON")
            print(f"      Preview: {str(data)[:300]}")
        except:
            print(f"      Type: {response.headers.get('Content-Type')}")
            print(f"      Preview: {response.text[:300]}")
    elif response.status_code == 404:
        print(f"   ❌ Not found: {endpoint}")
    else:
        print(f"   ⚠️  {endpoint} -> {response.status_code}: {response.text[:100]}")

# Test 4: Check if we can get specific instrument data
print("\n\n4️⃣  TESTING SPECIFIC INSTRUMENT QUERY")

# Try to get data for a specific ETH option
test_params = [
    {"underlying": "ETH"},
    {"currency": "ETH"},
    {"symbol": "ETH"},
    {"instrument": "ETH-27OCT25-2400-C"},
]

for params in test_params:
    url = f"{BASE_URL}/data/summary/deribit/options/greeks/"
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        print(f"\n   ✅ Params {params} worked!")
        print(f"      Records: {len(data) if isinstance(data, list) else 'dict'}")
        if isinstance(data, list) and len(data) > 0:
            print(f"      Sample: {json.dumps(data[0], indent=2)[:300]}")
        break

print("\n" + "=" * 80)
print("EXPLORATION COMPLETE")
print("=" * 80)
