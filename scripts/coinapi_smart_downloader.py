#!/usr/bin/env python3
"""
CoinAPI Smart Options Downloader
Maximize $30 credit by downloading most recent data first
Strategy: Recent data is most valuable for IV calculations
"""

import os
import requests
import psycopg2
import time
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import re

# Load environment
load_dotenv()

API_KEY = os.getenv('COINAPI_KEY')
BASE_URL = "https://rest.coinapi.io/v1"
DB_CONN_STR = "dbname=crypto_data user=postgres"

# Configuration
RATE_LIMIT_DELAY = 0.1  # 100ms between requests (10 req/sec)
MAX_REQUESTS = 10000     # Safety limit to avoid burning through all credit
REQUEST_COST = 0.003     # Estimated $0.003 per OHLCV request
BUDGET = 30.0            # $30 budget

# Download strategy: Most recent first
DAYS_BACK_START = 7      # Start with last 7 days
DAYS_BACK_MAX = 90       # Go back max 90 days with remaining budget

class CoinAPIDownloader:
    def __init__(self):
        self.api_key = API_KEY
        self.base_url = BASE_URL
        self.headers = {"X-CoinAPI-Key": self.api_key}
        self.db_conn = None
        self.requests_made = 0
        self.cost_spent = 0.0
        self.records_inserted = 0

    def connect_db(self):
        """Connect to PostgreSQL"""
        self.db_conn = psycopg2.connect(DB_CONN_STR)

    def parse_symbol(self, symbol_id):
        """
        Parse CoinAPI symbol into components
        Example: DERIBIT_OPT_BTC_USD_251031_170000_P
        """
        match = re.match(r'DERIBIT_OPT_(\w+)_(USD|USDC)_(\d{6})_(\d+)_([CP])', symbol_id)

        if match:
            currency = match.group(1)  # BTC or ETH
            expiry_str = match.group(3)  # 251031
            strike = float(match.group(4))  # 170000
            option_type = match.group(5)  # C or P

            # Parse expiry date: 251031 -> 2025-10-31
            year = 2000 + int(expiry_str[:2])
            month = int(expiry_str[2:4])
            day = int(expiry_str[4:6])
            expiry_date = f"{year}-{month:02d}-{day:02d}"

            return {
                'currency': currency,
                'strike': strike,
                'expiry_date': expiry_date,
                'option_type': option_type
            }

        return None

    def get_recent_btc_eth_options(self):
        """Get list of active BTC and ETH options"""
        print("\n📋 Fetching active BTC and ETH options...")

        url = f"{self.base_url}/symbols/DERIBIT"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"❌ Failed to get symbols: {response.status_code}")
            return []

        symbols = response.json()

        # Filter for options only
        options = [s for s in symbols
                  if s.get('symbol_type') == 'OPTION'
                  and ('BTC' in s.get('symbol_id', '') or 'ETH' in s.get('symbol_id', ''))]

        print(f"✅ Found {len(options)} BTC/ETH options")

        # Sort by expiry date (most recent first)
        def get_expiry_sort_key(symbol):
            sid = symbol.get('symbol_id', '')
            match = re.search(r'_(\d{6})_', sid)
            if match:
                expiry_str = match.group(1)
                return expiry_str
            return '999999'  # Far future for unparseable

        options.sort(key=get_expiry_sort_key, reverse=True)

        return options

    def download_ohlcv(self, symbol_id, days_back=7, period_id="1MIN"):
        """Download OHLCV data for a symbol"""
        time_end = datetime.now(timezone.utc)
        time_start = time_end - timedelta(days=days_back)

        url = f"{self.base_url}/ohlcv/{symbol_id}/history"
        params = {
            "period_id": period_id,
            "time_start": time_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "time_end": time_end.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "limit": 10000  # Max per request
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            self.requests_made += 1
            self.cost_spent += REQUEST_COST

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                print(f"\n❌ Budget exhausted! (403 Forbidden)")
                return None
            else:
                return []

        except Exception as e:
            print(f"   Error: {e}")
            return []

    def insert_data(self, symbol_id, data, period_id):
        """Insert OHLCV data into database"""
        if not data:
            return 0

        parsed = self.parse_symbol(symbol_id)
        if not parsed:
            return 0

        cursor = self.db_conn.cursor()

        inserted = 0
        for candle in data:
            try:
                cursor.execute("""
                    INSERT INTO coinapi_options_ohlcv
                        (time_period_start, time_period_end, time_open, time_close,
                         symbol_id, currency, strike, expiry_date, option_type,
                         price_open, price_high, price_low, price_close,
                         volume_traded, trades_count, period_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol_id, time_period_start, period_id) DO NOTHING
                """, (
                    candle['time_period_start'],
                    candle['time_period_end'],
                    candle.get('time_open'),
                    candle.get('time_close'),
                    symbol_id,
                    parsed['currency'],
                    parsed['strike'],
                    parsed['expiry_date'],
                    parsed['option_type'],
                    candle.get('price_open'),
                    candle.get('price_high'),
                    candle.get('price_low'),
                    candle.get('price_close'),
                    candle.get('volume_traded'),
                    candle.get('trades_count'),
                    period_id
                ))
                inserted += 1

            except Exception as e:
                print(f"   DB Error: {e}")
                continue

        self.db_conn.commit()
        self.records_inserted += inserted
        return inserted

    def run_smart_download(self):
        """Main download logic: Most recent data first"""
        print("=" * 80)
        print("COINAPI SMART OPTIONS DOWNLOADER")
        print("=" * 80)
        print(f"Budget: ${BUDGET}")
        print(f"Estimated requests: ~{int(BUDGET / REQUEST_COST)}")
        print(f"Strategy: Download most recent data first (last {DAYS_BACK_START} days)")
        print("=" * 80)

        self.connect_db()

        # Get list of options
        options = self.get_recent_btc_eth_options()

        if not options:
            print("❌ No options found")
            return

        print(f"\n🎯 Download Plan:")
        print(f"   Phase 1: Last {DAYS_BACK_START} days for all options")
        print(f"   Phase 2: Extend to {DAYS_BACK_MAX} days if budget allows")
        print(f"   Priority: Active options > Recently expired")

        # Phase 1: Last 7 days for all options
        print(f"\n" + "=" * 80)
        print(f"PHASE 1: DOWNLOADING LAST {DAYS_BACK_START} DAYS")
        print("=" * 80)

        for i, option in enumerate(options):
            symbol_id = option['symbol_id']

            # Check budget
            if self.cost_spent >= BUDGET:
                print(f"\n💰 Budget exhausted: ${self.cost_spent:.2f} / ${BUDGET}")
                break

            if self.requests_made >= MAX_REQUESTS:
                print(f"\n⚠️ Request limit reached: {self.requests_made}")
                break

            print(f"\n[{i+1}/{len(options)}] {symbol_id}")
            print(f"   Budget: ${self.cost_spent:.2f} / ${BUDGET} | Requests: {self.requests_made}")

            # Download 1-minute data for last 7 days
            data = self.download_ohlcv(symbol_id, days_back=DAYS_BACK_START, period_id="1MIN")

            if data is None:  # Budget exhausted
                break

            if len(data) > 0:
                inserted = self.insert_data(symbol_id, data, "1MIN")
                print(f"   ✅ Downloaded {len(data)} candles, inserted {inserted}")
            else:
                print(f"   ⚠️ No data available")

            # Rate limit
            time.sleep(RATE_LIMIT_DELAY)

        # Phase 2: Extend to 90 days if budget allows
        remaining_budget = BUDGET - self.cost_spent
        remaining_requests = int(remaining_budget / REQUEST_COST)

        if remaining_requests > 10:
            print(f"\n" + "=" * 80)
            print(f"PHASE 2: EXTENDING TO {DAYS_BACK_MAX} DAYS")
            print(f"Remaining budget: ${remaining_budget:.2f} (~{remaining_requests} requests)")
            print("=" * 80)

            # Download older data for most important options (first 100)
            for i, option in enumerate(options[:min(100, remaining_requests)]):
                symbol_id = option['symbol_id']

                if self.cost_spent >= BUDGET:
                    break

                print(f"\n[{i+1}/100] {symbol_id} - Extending to {DAYS_BACK_MAX} days")

                # Download from day 8 to day 90
                time_end = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK_START)
                time_start = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK_MAX)

                url = f"{self.base_url}/ohlcv/{symbol_id}/history"
                params = {
                    "period_id": "1MIN",
                    "time_start": time_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "time_end": time_end.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "limit": 10000
                }

                try:
                    response = requests.get(url, headers=self.headers, params=params)
                    self.requests_made += 1
                    self.cost_spent += REQUEST_COST

                    if response.status_code == 200:
                        data = response.json()
                        if len(data) > 0:
                            inserted = self.insert_data(symbol_id, data, "1MIN")
                            print(f"   ✅ +{len(data)} candles, inserted {inserted}")

                except Exception as e:
                    print(f"   Error: {e}")

                time.sleep(RATE_LIMIT_DELAY)

        # Final summary
        print(f"\n" + "=" * 80)
        print("DOWNLOAD COMPLETE!")
        print("=" * 80)
        print(f"📊 Statistics:")
        print(f"   Requests made: {self.requests_made}")
        print(f"   Estimated cost: ${self.cost_spent:.2f}")
        print(f"   Records inserted: {self.records_inserted}")
        print(f"   Options processed: {min(i+1, len(options))}")
        print("=" * 80)

        # Close connection
        self.db_conn.close()


def main():
    downloader = CoinAPIDownloader()
    downloader.run_smart_download()


if __name__ == "__main__":
    main()
