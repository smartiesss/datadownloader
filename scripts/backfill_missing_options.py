#!/usr/bin/env python3
"""
Backfill Missing Options Data from CryptoDataDownload
Identifies symbols that failed due to rate limiting and retries them
"""

import os
import requests
import psycopg2
import time
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('CRYPTODATADOWNLOAD_API_KEY')
BASE_URL = "https://api.cryptodatadownload.com/v1"
DB_CONN_STR = "dbname=crypto_data user=postgres"

# IMPORTANT: Slower rate to avoid hitting limits again
RATE_LIMIT_DELAY = 1.0  # 1 second between requests (1 req/sec)

class BackfillDownloader:
    def __init__(self):
        self.api_key = API_KEY
        self.base_url = BASE_URL
        self.headers = {"Authorization": f"Token {self.api_key}"}
        self.db_conn = None
        self.requests_made = 0
        self.records_inserted = 0
        self.symbols_processed = 0
        self.rate_limit_hits = 0

    def connect_db(self):
        """Connect to PostgreSQL"""
        self.db_conn = psycopg2.connect(DB_CONN_STR)

    def parse_symbol(self, symbol):
        """Parse CryptoDataDownload symbol"""
        match = re.match(r'(BTC|ETH)-(\d{2})([A-Z]{3})(\d{2})-(\d+)-([CP])', symbol)

        if match:
            currency = match.group(1)
            day = match.group(2)
            month_str = match.group(3)
            year = match.group(4)
            strike = float(match.group(5))
            option_type = match.group(6)

            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            month = month_map.get(month_str)

            if not month:
                return None

            year_full = 2000 + int(year)
            expiry_date = f"{year_full}-{month:02d}-{int(day):02d}"

            return {
                'currency': currency,
                'strike': strike,
                'expiry_date': expiry_date,
                'option_type': option_type
            }

        return None

    def get_available_options(self, currency='ETH'):
        """Get list of available options for a currency"""
        print(f"\n📋 Fetching available {currency} options...")

        url = f"{self.base_url}/data/ohlc/deribit/options/available/"
        response = requests.get(url, headers={"Token": self.api_key})

        if response.status_code != 200:
            print(f"❌ Failed to get options list: {response.status_code}")
            return []

        data = response.json()
        all_options = data.get('result', [])

        # Filter by currency
        currency_options = [opt for opt in all_options if opt.startswith(currency)]

        print(f"✅ Found {len(currency_options)} {currency} options")
        return currency_options

    def get_downloaded_symbols(self, currency='ETH'):
        """Get list of symbols already downloaded"""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT DISTINCT symbol
            FROM cryptodatadownload_options_daily
            WHERE currency = %s
        """, (currency,))

        downloaded = set(row[0] for row in cursor.fetchall())
        print(f"✅ Found {len(downloaded)} {currency} symbols already downloaded")
        return downloaded

    def download_ohlcv(self, symbol, retry_count=0):
        """Download daily OHLCV data with rate limit handling"""
        url = f"{self.base_url}/data/ohlc/deribit/options/"
        params = {"symbol": symbol}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            self.requests_made += 1

            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])

            elif response.status_code == 404:
                return []

            elif response.status_code == 429:
                self.rate_limit_hits += 1

                # Parse the throttle message
                try:
                    error_data = response.json()
                    detail = error_data.get('detail', '')
                    # Extract seconds from "Expected available in X seconds"
                    import re
                    match = re.search(r'(\d+) seconds', detail)
                    if match:
                        wait_seconds = int(match.group(1))
                        print(f"   ⚠️  Rate limit hit! Must wait {wait_seconds} seconds ({wait_seconds/60:.1f} minutes)")
                        print(f"   💤 Sleeping until rate limit resets...")
                        time.sleep(wait_seconds + 5)  # Add 5 seconds buffer
                        print(f"   ✅ Resuming downloads...")
                        return self.download_ohlcv(symbol, retry_count + 1)
                except:
                    # Default wait if we can't parse the message
                    print(f"   ⚠️  Rate limit hit! Waiting 60 seconds...")
                    time.sleep(60)
                    return self.download_ohlcv(symbol, retry_count + 1)

            else:
                print(f"   ⚠️  Error {response.status_code}: {response.text[:100]}")
                return []

        except requests.exceptions.Timeout:
            print(f"   ⚠️  Timeout for {symbol}")
            if retry_count < 2:
                time.sleep(5)
                return self.download_ohlcv(symbol, retry_count + 1)
            return []

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []

    def insert_data(self, symbol, data):
        """Insert daily OHLCV data into database"""
        if not data:
            return 0

        parsed = self.parse_symbol(symbol)
        if not parsed:
            print(f"   ⚠️  Could not parse symbol: {symbol}")
            return 0

        cursor = self.db_conn.cursor()
        inserted = 0

        for candle in data:
            try:
                cursor.execute("""
                    INSERT INTO cryptodatadownload_options_daily
                        (unix_timestamp, date, symbol, currency, expiry_date, strike, option_type,
                         price_open, price_high, price_low, price_close, volume_traded)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, date) DO NOTHING
                """, (
                    candle['unix'],
                    candle['date'],
                    symbol,
                    parsed['currency'],
                    parsed['expiry_date'],
                    parsed['strike'],
                    parsed['option_type'],
                    float(candle['open']) if candle['open'] else None,
                    float(candle['high']) if candle['high'] else None,
                    float(candle['low']) if candle['low'] else None,
                    float(candle['close']) if candle['close'] else None,
                    float(candle['volume']) if candle['volume'] else 0.0,
                ))
                inserted += 1

            except Exception as e:
                print(f"   DB Error for {symbol} on {candle.get('date')}: {e}")
                continue

        self.db_conn.commit()
        self.records_inserted += inserted
        return inserted

    def backfill(self, currency='ETH'):
        """Main backfill logic"""
        print("=" * 80)
        print("CRYPTODATADOWNLOAD BACKFILL - MISSING OPTIONS")
        print("=" * 80)
        print(f"Currency: {currency}")
        print(f"Rate limit: {RATE_LIMIT_DELAY}s between requests (SLOW to avoid throttling)")
        print("=" * 80)

        self.connect_db()

        # Get all available options
        all_options = self.get_available_options(currency)

        if not all_options:
            print("❌ No options found")
            return

        # Get already downloaded symbols
        downloaded = self.get_downloaded_symbols(currency)

        # Find missing symbols
        missing = [opt for opt in all_options if opt not in downloaded]

        print(f"\n🎯 Backfill Plan:")
        print(f"   Total {currency} options: {len(all_options)}")
        print(f"   Already downloaded: {len(downloaded)}")
        print(f"   Missing (to backfill): {len(missing)}")
        print(f"   Estimated time: ~{len(missing) * RATE_LIMIT_DELAY / 60:.1f} minutes")

        if len(missing) == 0:
            print("\n✅ No missing options! All data already downloaded.")
            return

        # Download missing options
        print(f"\n" + "=" * 80)
        print(f"BACKFILLING {len(missing)} MISSING OPTIONS")
        print("=" * 80)

        for i, symbol in enumerate(missing):
            print(f"\n[{i+1}/{len(missing)}] {symbol}")
            print(f"   Progress: {(i+1)/len(missing)*100:.1f}% | Requests: {self.requests_made} | Records: {self.records_inserted} | Rate limits: {self.rate_limit_hits}")

            # Download data
            data = self.download_ohlcv(symbol)

            if len(data) > 0:
                inserted = self.insert_data(symbol, data)
                print(f"   ✅ Downloaded {len(data)} days, inserted {inserted} records")
                self.symbols_processed += 1
            else:
                print(f"   ⚠️  No data available (may be new/unlisted option)")

            # Rate limit delay
            if i < len(missing) - 1:
                time.sleep(RATE_LIMIT_DELAY)

        # Final summary
        print(f"\n" + "=" * 80)
        print("BACKFILL COMPLETE!")
        print("=" * 80)
        print(f"📊 Statistics:")
        print(f"   Symbols backfilled: {self.symbols_processed}/{len(missing)}")
        print(f"   API requests made: {self.requests_made}")
        print(f"   Daily records inserted: {self.records_inserted}")
        print(f"   Rate limit hits: {self.rate_limit_hits}")
        print(f"   Average days per option: {self.records_inserted/max(self.symbols_processed,1):.1f}")
        print("=" * 80)

        self.db_conn.close()


def main():
    import sys

    currency = sys.argv[1] if len(sys.argv) > 1 else 'ETH'

    downloader = BackfillDownloader()
    downloader.backfill(currency=currency)


if __name__ == "__main__":
    main()
