#!/usr/bin/env python3
"""
CoinAPI Deribit Options Data Explorer
Once you add credits to your CoinAPI account, this will:
1. List available Deribit option symbols
2. Fetch historical OHLCV data (1-minute, 5-minute, etc.)
3. Fetch current quotes with Greeks and IV (if available)
4. Show data structure for database integration
"""

import requests
import json
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
API_KEY = os.getenv('COINAPI_KEY', 'b4f3a3df-e4b4-4032-aa94-dab7ab9ee4c9')
BASE_URL = "https://rest.coinapi.io/v1"

class CoinAPIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {"X-CoinAPI-Key": api_key}
        self.base_url = BASE_URL

    def check_quota(self):
        """Check API quota and subscription status"""
        print("=" * 80)
        print("CHECKING API QUOTA")
        print("=" * 80)

        url = f"{self.base_url}/exchangerate/BTC/USD"
        response = requests.get(url, headers=self.headers)

        print(f"Status: {response.status_code}")

        if response.status_code == 403:
            error_data = response.json()
            print(f"\n❌ SUBSCRIPTION REQUIRED")
            print(f"   Error: {error_data.get('error')}")
            print(f"   Quota Key: {error_data.get('QuotaKey')}")
            print(f"   Current Usage: ${error_data.get('QuotaValueCurrentUsage')}")
            print(f"   Quota Limit: ${error_data.get('QuotaValue')}")
            print(f"\n   ACTION REQUIRED:")
            print(f"   1. Go to: https://www.coinapi.io/market-data-api/pricing")
            print(f"   2. Add credits or subscribe to a plan")
            print(f"   3. Professional plan (~$300/month) required for options data")
            print(f"   4. Or add $25 credits to test with free plan")
            return False
        elif response.status_code == 200:
            print(f"✅ API Key Valid and Active")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Unexpected Error: {response.text}")
            return False

    def get_exchanges(self):
        """List all available exchanges"""
        print("\n" + "=" * 80)
        print("AVAILABLE EXCHANGES")
        print("=" * 80)

        url = f"{self.base_url}/exchanges"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            exchanges = response.json()
            deribit = [ex for ex in exchanges if 'DERIBIT' in ex.get('exchange_id', '')]

            if deribit:
                print(f"✅ Found Deribit exchange:")
                print(json.dumps(deribit[0], indent=2))
            else:
                print(f"⚠️  Deribit not found in exchange list")

            return exchanges
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
            return []

    def get_deribit_option_symbols(self, limit=50):
        """Get Deribit option symbols"""
        print("\n" + "=" * 80)
        print("DERIBIT OPTION SYMBOLS")
        print("=" * 80)

        url = f"{self.base_url}/symbols/DERIBIT"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            symbols = response.json()

            # Filter for options
            options = [s for s in symbols if s.get('symbol_type') == 'OPTION']

            print(f"✅ Found {len(options)} option symbols\n")

            # Group by asset
            btc_options = [o for o in options if 'BTC' in o.get('asset_id_base', '')]
            eth_options = [o for o in options if 'ETH' in o.get('asset_id_base', '')]

            print(f"BTC Options: {len(btc_options)}")
            print(f"ETH Options: {len(eth_options)}")

            print(f"\nSample BTC Options (first 10):")
            for opt in btc_options[:10]:
                symbol_id = opt.get('symbol_id')
                option_type = 'CALL' if opt.get('option_type_is_call') else 'PUT'
                strike = opt.get('option_strike_price')
                expiry = opt.get('option_expiration_time')

                print(f"  {symbol_id}")
                print(f"    Type: {option_type}, Strike: ${strike}, Expiry: {expiry}")

            return options
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
            return []

    def get_option_ohlcv(self, symbol_id, period="1MIN", days_back=7, limit=100):
        """
        Get historical OHLCV data for an option

        Args:
            symbol_id: CoinAPI symbol ID (e.g., "DERIBIT_OPTION_BTC_USDC_240927_70000_C")
            period: Time period - "1MIN", "5MIN", "15MIN", "1HRS", "1DAY"
            days_back: How many days of history to fetch
            limit: Max records to return
        """
        print("\n" + "=" * 80)
        print(f"OPTION OHLCV DATA: {symbol_id}")
        print(f"Period: {period}, Days: {days_back}, Limit: {limit}")
        print("=" * 80)

        time_end = datetime.utcnow()
        time_start = time_end - timedelta(days=days_back)

        url = f"{self.base_url}/ohlcv/{symbol_id}/history"
        params = {
            "period_id": period,
            "time_start": time_start.isoformat(),
            "time_end": time_end.isoformat(),
            "limit": limit
        }

        print(f"Request URL: {url}")
        print(f"Params: {json.dumps(params, indent=2)}")

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Received {len(data)} OHLCV candles")

            if len(data) > 0:
                print(f"\nFirst Candle:")
                print(json.dumps(data[0], indent=2))

                print(f"\nLast 5 Candles:")
                print(f"{'Timestamp':<25} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
                print("-" * 90)
                for candle in data[-5:]:
                    timestamp = candle.get('time_period_start', 'N/A')
                    o = candle.get('price_open', 0)
                    h = candle.get('price_high', 0)
                    l = candle.get('price_low', 0)
                    c = candle.get('price_close', 0)
                    v = candle.get('volume_traded', 0)
                    print(f"{timestamp:<25} {o:>10.4f} {h:>10.4f} {l:>10.4f} {c:>10.4f} {v:>12.6f}")

                # Analyze data structure for database mapping
                print(f"\n📊 DATA STRUCTURE ANALYSIS:")
                sample = data[0]
                print(f"Available Fields:")
                for key in sample.keys():
                    print(f"  - {key}: {type(sample[key]).__name__}")

            else:
                print(f"⚠️  No data returned (option may be expired or inactive)")

            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
            return []

    def get_option_quotes_current(self, symbol_id):
        """
        Get current quote data for option (may include Greeks and IV)
        """
        print("\n" + "=" * 80)
        print(f"CURRENT QUOTE DATA: {symbol_id}")
        print("=" * 80)

        url = f"{self.base_url}/quotes/{symbol_id}/current"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Received current quote\n")
            print(json.dumps(data, indent=2))

            # Check for Greeks and IV
            print(f"\n📊 CHECKING FOR GREEKS & IV:")

            fields_to_check = [
                'implied_volatility', 'iv', 'mark_iv',
                'delta', 'gamma', 'vega', 'theta', 'rho',
                'bid_price', 'ask_price', 'mark_price'
            ]

            for field in fields_to_check:
                if field in data:
                    print(f"  ✅ {field}: {data[field]}")
                else:
                    print(f"  ❌ {field}: Not available")

            return data
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
            return None

    def test_multiple_periods(self, symbol_id):
        """Test different time periods to see what's available"""
        print("\n" + "=" * 80)
        print(f"TESTING MULTIPLE TIME PERIODS FOR: {symbol_id}")
        print("=" * 80)

        periods = ["1MIN", "5MIN", "15MIN", "1HRS", "1DAY"]
        results = {}

        for period in periods:
            print(f"\nTesting {period}...")
            url = f"{self.base_url}/ohlcv/{symbol_id}/history"

            time_end = datetime.utcnow()
            time_start = time_end - timedelta(days=3)

            params = {
                "period_id": period,
                "time_start": time_start.isoformat(),
                "time_end": time_end.isoformat(),
                "limit": 10
            }

            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                data = response.json()
                results[period] = len(data)
                print(f"  ✅ {period}: {len(data)} candles available")
            else:
                results[period] = 0
                print(f"  ❌ {period}: Not available")

            time.sleep(0.5)  # Rate limit courtesy

        print(f"\n📊 SUMMARY:")
        for period, count in results.items():
            status = "✅ Available" if count > 0 else "❌ Not available"
            print(f"  {period}: {status} ({count} candles)")

        return results


def main():
    """Main test flow"""
    print("\n" + "=" * 80)
    print("COINAPI DERIBIT OPTIONS DATA EXPLORER")
    print("=" * 80)
    print(f"API Key: {API_KEY[:20]}...{API_KEY[-10:]}")
    print(f"Base URL: {BASE_URL}")
    print("=" * 80 + "\n")

    client = CoinAPIClient(API_KEY)

    # Step 1: Check quota
    if not client.check_quota():
        print("\n" + "=" * 80)
        print("⚠️  CANNOT PROCEED: No active subscription")
        print("=" * 80)
        print("\nTO FIX:")
        print("1. Visit: https://www.coinapi.io/pricing")
        print("2. Add credits ($25 minimum) or subscribe to a plan")
        print("3. For options data, you likely need Professional plan (~$300/month)")
        print("4. Or contact sales for a trial")
        print("\nALTERNATIVE:")
        print("Use Deribit API directly (FREE) to backfill options data")
        print("Run: python3 scripts/backfill_options.py")
        print("=" * 80 + "\n")
        return

    # Step 2: Get exchanges
    exchanges = client.get_exchanges()

    # Step 3: Get Deribit option symbols
    options = client.get_deribit_option_symbols()

    if not options:
        print("\n❌ No options found. Cannot proceed.")
        return

    # Step 4: Test with a BTC option
    btc_options = [o for o in options if 'BTC' in o.get('asset_id_base', '')]

    if btc_options:
        # Pick a recent option (first one)
        test_option = btc_options[0]
        symbol_id = test_option['symbol_id']

        print(f"\n" + "=" * 80)
        print(f"TESTING WITH SYMBOL: {symbol_id}")
        print("=" * 80)

        # Test OHLCV data
        ohlcv_1min = client.get_option_ohlcv(symbol_id, period="1MIN", days_back=3, limit=100)

        # Test current quotes
        quotes = client.get_option_quotes_current(symbol_id)

        # Test multiple periods
        period_results = client.test_multiple_periods(symbol_id)

    # Final summary
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\n✅ If you can see data above, CoinAPI is working!")
    print("\n📊 NEXT STEPS:")
    print("1. Verify 1-minute data is available (check period_results)")
    print("2. Check if Greeks (Delta, Gamma, Vega) are in quotes")
    print("3. Map data structure to your database schema")
    print("4. Estimate cost for full historical download")
    print("5. Build historical downloader script")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
