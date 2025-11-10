#!/usr/bin/env python3
"""
Verify Deribit Historical Options Data Availability
Tests what historical data is actually available from Deribit API
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Use mainnet credentials
CLIENT_ID = os.getenv('MAINNET_DERIBIT_CLIENT_ID')
CLIENT_SECRET = os.getenv('MAINNET_DERIBIT_CLIENT_SECRET')
BASE_URL = "https://www.deribit.com/api/v2"

class DeribitHistoricalChecker:
    def __init__(self):
        self.base_url = BASE_URL
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET

    def get_instruments(self, currency="BTC", kind="option", expired=False):
        """Get list of option instruments"""
        print("=" * 80)
        print(f"FETCHING {currency} {kind.upper()} INSTRUMENTS (expired={expired})")
        print("=" * 80)

        url = f"{self.base_url}/public/get_instruments"
        params = {
            "currency": currency,
            "kind": kind,
            "expired": str(expired).lower()
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('result'):
                instruments = data['result']
                print(f"✅ Found {len(instruments)} {currency} {kind}s (expired={expired})")

                if instruments:
                    print(f"\nSample instruments:")
                    for inst in instruments[:5]:
                        print(f"  - {inst['instrument_name']}: Strike ${inst.get('strike')}, Expiry: {inst.get('expiration_timestamp')}")

                return instruments
            else:
                print(f"❌ No instruments found")
                return []

        except Exception as e:
            print(f"❌ Error: {e}")
            return []

    def check_tradingview_chart_data(self, instrument_name, resolution=60):
        """
        Check if /get_tradingview_chart_data endpoint works for options
        This is what you use for futures - let's see if it works for options
        """
        print("\n" + "=" * 80)
        print(f"TESTING TRADINGVIEW CHART DATA FOR: {instrument_name}")
        print(f"Resolution: {resolution} minutes")
        print("=" * 80)

        url = f"{self.base_url}/public/get_tradingview_chart_data"

        # Try to get last 30 days
        end_timestamp = int(datetime.now().timestamp() * 1000)
        start_timestamp = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)

        params = {
            "instrument_name": instrument_name,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "resolution": resolution
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if response.status_code == 200 and data.get('result'):
                result = data['result']

                ticks = result.get('ticks', [])
                open_prices = result.get('open', [])
                close_prices = result.get('close', [])
                high_prices = result.get('high', [])
                low_prices = result.get('low', [])
                volumes = result.get('volume', [])

                print(f"✅ SUCCESS! TradingView chart data available")
                print(f"   Candles received: {len(ticks)}")
                print(f"   Date range: {datetime.fromtimestamp(ticks[0]/1000)} to {datetime.fromtimestamp(ticks[-1]/1000)}")
                print(f"   Status: {result.get('status')}")

                if len(ticks) > 0:
                    print(f"\n   Last 5 candles:")
                    print(f"   {'Timestamp':<20} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>10}")
                    print(f"   {'-' * 75}")

                    for i in range(max(0, len(ticks)-5), len(ticks)):
                        timestamp = datetime.fromtimestamp(ticks[i]/1000).strftime('%Y-%m-%d %H:%M')
                        print(f"   {timestamp:<20} {open_prices[i]:>10.4f} {high_prices[i]:>10.4f} {low_prices[i]:>10.4f} {close_prices[i]:>10.4f} {volumes[i]:>10.2f}")

                return True, len(ticks)
            else:
                error = data.get('error', {})
                print(f"❌ FAILED: {error.get('message', 'Unknown error')}")
                print(f"   Full response: {json.dumps(data, indent=2)}")
                return False, 0

        except Exception as e:
            print(f"❌ Error: {e}")
            return False, 0

    def check_ticker_data(self, instrument_name):
        """
        Check /ticker endpoint - this gives current bid/ask/IV/Greeks
        """
        print("\n" + "=" * 80)
        print(f"TESTING TICKER DATA FOR: {instrument_name}")
        print("=" * 80)

        url = f"{self.base_url}/public/ticker"
        params = {"instrument_name": instrument_name}

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if response.status_code == 200 and data.get('result'):
                result = data['result']

                print(f"✅ Ticker data available")
                print(f"\n   Current snapshot:")
                print(f"   Best Bid: {result.get('best_bid_price')}")
                print(f"   Best Ask: {result.get('best_ask_price')}")
                print(f"   Mark Price: {result.get('mark_price')}")
                print(f"   Mark IV: {result.get('mark_iv')}%")
                print(f"   Bid IV: {result.get('bid_iv')}%")
                print(f"   Ask IV: {result.get('ask_iv')}%")
                print(f"   Underlying Price: ${result.get('underlying_price')}")

                greeks = result.get('greeks', {})
                if greeks:
                    print(f"\n   Greeks:")
                    print(f"   Delta: {greeks.get('delta')}")
                    print(f"   Gamma: {greeks.get('gamma')}")
                    print(f"   Vega: {greeks.get('vega')}")
                    print(f"   Theta: {greeks.get('theta')}")
                    print(f"   Rho: {greeks.get('rho')}")

                return True
            else:
                print(f"❌ FAILED")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def test_expired_option(self):
        """
        Critical test: Can we get historical data for EXPIRED options?
        """
        print("\n" + "=" * 80)
        print("CRITICAL TEST: EXPIRED OPTIONS HISTORICAL DATA")
        print("=" * 80)

        # Get expired BTC options
        expired_options = self.get_instruments(currency="BTC", kind="option", expired=True)

        if not expired_options:
            print("❌ No expired options found")
            return False

        # Try to get chart data for an expired option
        test_option = expired_options[0]
        instrument_name = test_option['instrument_name']

        print(f"\n📊 Testing with expired option: {instrument_name}")
        print(f"   Expiration: {datetime.fromtimestamp(test_option['expiration_timestamp']/1000)}")

        success, candles = self.check_tradingview_chart_data(instrument_name, resolution=60)

        if success:
            print(f"\n✅ EXCELLENT! We CAN get historical data for expired options!")
            print(f"   This means we can backfill old options data")
            return True
        else:
            print(f"\n❌ PROBLEM! Cannot get historical data for expired options")
            print(f"   This means Deribit API may not support historical options backfill")
            return False

    def test_active_option(self):
        """
        Test: Can we get historical data for ACTIVE (non-expired) options?
        """
        print("\n" + "=" * 80)
        print("TEST: ACTIVE OPTIONS HISTORICAL DATA")
        print("=" * 80)

        # Get active BTC options
        active_options = self.get_instruments(currency="BTC", kind="option", expired=False)

        if not active_options:
            print("❌ No active options found")
            return False

        # Find a relatively old active option (closest to expiry)
        # Sort by expiration timestamp
        sorted_options = sorted(active_options, key=lambda x: x['expiration_timestamp'])

        test_option = sorted_options[0]  # Get the soonest to expire
        instrument_name = test_option['instrument_name']

        print(f"\n📊 Testing with active option: {instrument_name}")
        print(f"   Expiration: {datetime.fromtimestamp(test_option['expiration_timestamp']/1000)}")
        print(f"   Strike: ${test_option.get('strike')}")

        # Test TradingView chart data
        success, candles = self.check_tradingview_chart_data(instrument_name, resolution=60)

        if success and candles > 0:
            print(f"\n✅ SUCCESS! We CAN get historical data for active options")
            print(f"   Received {candles} candles")
            return True
        else:
            print(f"\n⚠️  LIMITED! Only {candles} candles available")
            return False

    def test_different_resolutions(self, instrument_name):
        """
        Test what resolutions are available: 1min, 5min, 15min, 60min, 1D
        """
        print("\n" + "=" * 80)
        print(f"TESTING DIFFERENT RESOLUTIONS FOR: {instrument_name}")
        print("=" * 80)

        resolutions = {
            "1": "1 minute",
            "5": "5 minutes",
            "15": "15 minutes",
            "60": "1 hour",
            "D": "1 day"
        }

        results = {}

        for res_id, res_name in resolutions.items():
            print(f"\nTesting {res_name}...")

            url = f"{self.base_url}/public/get_tradingview_chart_data"
            end_timestamp = int(datetime.now().timestamp() * 1000)
            start_timestamp = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)

            params = {
                "instrument_name": instrument_name,
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
                "resolution": res_id
            }

            try:
                response = requests.get(url, params=params)
                data = response.json()

                if response.status_code == 200 and data.get('result'):
                    ticks = data['result'].get('ticks', [])
                    results[res_name] = len(ticks)
                    print(f"  ✅ {res_name}: {len(ticks)} candles")
                else:
                    results[res_name] = 0
                    print(f"  ❌ {res_name}: Not available")

            except Exception as e:
                results[res_name] = 0
                print(f"  ❌ {res_name}: Error - {e}")

        print(f"\n📊 RESOLUTION SUMMARY:")
        for res_name, count in results.items():
            status = "✅ Available" if count > 0 else "❌ Not available"
            print(f"  {res_name}: {status} ({count} candles)")

        return results


def main():
    """Main verification flow"""
    print("\n" + "=" * 80)
    print("DERIBIT HISTORICAL OPTIONS DATA VERIFICATION")
    print("=" * 80)
    print(f"API: {BASE_URL}")
    print(f"Client ID: {CLIENT_ID}")
    print("=" * 80 + "\n")

    checker = DeribitHistoricalChecker()

    # Test 1: Get active BTC options
    print("📋 TEST 1: GET ACTIVE BTC OPTIONS")
    active_btc = checker.get_instruments(currency="BTC", kind="option", expired=False)

    # Test 2: Get active ETH options
    print("\n📋 TEST 2: GET ACTIVE ETH OPTIONS")
    active_eth = checker.get_instruments(currency="ETH", kind="option", expired=False)

    # Test 3: Get expired BTC options
    print("\n📋 TEST 3: GET EXPIRED BTC OPTIONS")
    expired_btc = checker.get_instruments(currency="BTC", kind="option", expired=True)

    # Test 4: Test historical data for active option
    print("\n📋 TEST 4: HISTORICAL DATA FOR ACTIVE OPTION")
    active_success = checker.test_active_option()

    # Test 5: CRITICAL - Test historical data for expired option
    print("\n📋 TEST 5: HISTORICAL DATA FOR EXPIRED OPTION (CRITICAL!)")
    expired_success = checker.test_expired_option()

    # Test 6: Test different resolutions
    if active_btc:
        print("\n📋 TEST 6: TEST DIFFERENT TIME RESOLUTIONS")
        test_instrument = active_btc[0]['instrument_name']
        resolution_results = checker.test_different_resolutions(test_instrument)

    # Test 7: Test ticker endpoint
    if active_btc:
        print("\n📋 TEST 7: TEST TICKER ENDPOINT (CURRENT DATA)")
        test_instrument = active_btc[0]['instrument_name']
        checker.check_ticker_data(test_instrument)

    # Final Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    print(f"\n📊 Available Instruments:")
    print(f"  Active BTC Options: {len(active_btc)}")
    print(f"  Active ETH Options: {len(active_eth)}")
    print(f"  Expired BTC Options: {len(expired_btc)}")

    print(f"\n📈 Historical Data Availability:")
    print(f"  Active options: {'✅ YES' if active_success else '❌ NO'}")
    print(f"  Expired options: {'✅ YES' if expired_success else '❌ NO'}")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if active_success and expired_success:
        print("✅ EXCELLENT! Deribit provides historical options data!")
        print("   You CAN backfill historical options using Deribit API (FREE)")
        print("   Recommended approach: Backfill from Deribit API directly")
    elif active_success and not expired_success:
        print("⚠️  PARTIAL! Deribit provides historical data for ACTIVE options only")
        print("   You can backfill recent options, but NOT old expired ones")
        print("   Recommendation: Use Deribit for recent, consider paid provider for old data")
    else:
        print("❌ LIMITED! Deribit may not provide sufficient historical options data")
        print("   Recommendation: Consider paid data providers (CryptoDataDownload, CoinAPI)")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
