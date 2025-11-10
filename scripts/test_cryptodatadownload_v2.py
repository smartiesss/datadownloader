#!/usr/bin/env python3
"""
CryptoDataDownload API Explorer v2
Test correct endpoints with proper authentication
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('CRYPTODATADOWNLOAD_API_KEY')
BASE_URL = "https://api.cryptodatadownload.com/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Token": API_KEY,  # Try both auth methods
}

print("=" * 80)
print("CRYPTODATADOWNLOAD API V2 - CORRECT ENDPOINTS")
print("=" * 80)
print(f"API Key: {API_KEY[:20]}...")
print("=" * 80)

# Test 1: List available Deribit options
print("\n1️⃣  LISTING AVAILABLE DERIBIT OPTIONS")
url = f"{BASE_URL}/data/ohlc/deribit/options/available/"

print(f"   Endpoint: {url}")

# Try with Bearer token
response = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"})
print(f"   Status (Bearer): {response.status_code}")

if response.status_code != 200:
    # Try with Token header
    response = requests.get(url, headers={"Token": API_KEY})
    print(f"   Status (Token): {response.status_code}")

if response.status_code != 200:
    # Try with query param
    response = requests.get(f"{url}?token={API_KEY}")
    print(f"   Status (Query): {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"   ✅ SUCCESS!")

    if isinstance(data, dict):
        print(f"\n   Response structure (keys): {list(data.keys())}")
        print(f"\n   Full response:")
        print(json.dumps(data, indent=2)[:2000])
    elif isinstance(data, list):
        print(f"\n   Total available options: {len(data)}")
        if len(data) > 0:
            print(f"\n   Sample options:")
            for i, opt in enumerate(data[:10]):
                print(f"   {i+1}. {opt}")
else:
    print(f"   ❌ FAILED: {response.status_code}")
    print(f"   Response: {response.text[:500]}")
    print(f"   Headers: {response.headers}")

# Test 2: Try to get OHLCV data for a specific option
print("\n\n2️⃣  TESTING OHLCV DATA ENDPOINT")
url = f"{BASE_URL}/data/ohlc/deribit/options/"

# Try different authentication methods
auth_methods = [
    {"Authorization": f"Bearer {API_KEY}"},
    {"Token": API_KEY},
    {},  # No header, use query param
]

for i, headers_to_try in enumerate(auth_methods):
    if i == 2:
        test_url = f"{url}?token={API_KEY}"
    else:
        test_url = url

    response = requests.get(test_url, headers=headers_to_try)

    print(f"\n   Auth method {i+1}: {response.status_code}")

    if response.status_code == 200:
        print(f"   ✅ SUCCESS with method {i+1}!")
        data = response.json()

        if isinstance(data, dict):
            print(f"      Response keys: {list(data.keys())}")

        print(f"      Response preview:")
        print(json.dumps(data, indent=2)[:1000])
        break
    elif response.status_code == 401 or response.status_code == 403:
        print(f"      Authentication issue")
    elif response.status_code == 400:
        print(f"      Bad request - might need parameters")
        print(f"      Response: {response.text[:200]}")

# Test 3: Try with specific parameters
print("\n\n3️⃣  TESTING WITH QUERY PARAMETERS")

test_params = [
    {"symbol": "ETH-27DEC24-2500-C"},
    {"currency": "ETH"},
    {"exchange": "deribit"},
    {"instrument": "ETH-27DEC24-2500-C"},
]

for params in test_params:
    url = f"{BASE_URL}/data/ohlc/deribit/options/"
    response = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"}, params=params)

    if response.status_code == 200:
        print(f"\n   ✅ Params {params} worked!")
        data = response.json()
        print(f"      Response type: {type(data)}")
        print(f"      Preview: {str(data)[:500]}")
        break
    elif response.status_code == 400:
        print(f"   ⚠️  Params {params} -> 400: {response.text[:200]}")
    else:
        print(f"   ❌ Params {params} -> {response.status_code}")

print("\n" + "=" * 80)
print("EXPLORATION COMPLETE")
print("=" * 80)
