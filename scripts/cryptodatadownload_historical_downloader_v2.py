#!/usr/bin/env python3
"""
CryptoDataDownload Historical Options Downloader (V2 - Rate Limit Aware)
Download daily OHLCV data for all available ETH options
Improvements:
- Exponential backoff on rate limits (429 errors)
- Better error handling with retries
- Automatic rate limit detection
- Configurable delays
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

# Rate limiting configuration
RATE_LIMIT_DELAY = 0.5  # Conservative 500ms between requests (2 req/sec)
MAX_RETRIES = 5
BACKOFF_MULTIPLIER = 2  # Double the wait time on each retry

class CryptoDataDownloadDownloader:
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
        """
        Parse CryptoDataDownload symbol into components
        Example: ETH-27DEC24-2500-C
        """
        # Pattern: {CURRENCY}-{DDMMMYY}-{STRIKE}-{TYPE}
        match = re.match(r'(BTC|ETH)-(\d{2})([A-Z]{3})(\d{2})-(\d+)-([CP])', symbol)

        if match:
            currency = match.group(1)
            day = match.group(2)
            month_str = match.group(3)
            year = match.group(4)
            strike = float(match.group(5))
            option_type = match.group(6)

            # Convert month string to number
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            month = month_map.get(month_str)

            if not month:
                return None

            # Parse year: 24 -> 2024
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

    def download_ohlcv(self, symbol, retry_count=0):
        """
        Download daily OHLCV data for a symbol with retry logic

        Handles rate limiting (429) with exponential backoff
        """
        url = f"{self.base_url}/data/ohlc/deribit/options/"
        params = {"symbol": symbol}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            self.requests_made += 1

            # Success
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])

            # Not found (expected for expired options)
            elif response.status_code == 404:
                return []

            # Rate limit hit
            elif response.status_code == 429:
                self.rate_limit_hits += 1

                if retry_count < MAX_RETRIES:
                    # Calculate backoff delay: double each time
                    backoff_delay = RATE_LIMIT_DELAY * (BACKOFF_MULTIPLIER ** retry_count)

                    print(f"   ⚠️  Rate limit hit (429). Waiting {backoff_delay:.1f}s before retry {retry_count+1}/{MAX_RETRIES}...")
                    time.sleep(backoff_delay)

                    # Retry
                    return self.download_ohlcv(symbol, retry_count + 1)
                else:
                    print(f"   ❌ Max retries exceeded for {symbol}")
                    return []

            # Server error
            elif response.status_code >= 500:
                if retry_count < MAX_RETRIES:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    print(f"   ⚠️  Server error {response.status_code}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    return self.download_ohlcv(symbol, retry_count + 1)
                else:
                    print(f"   ❌ Server error {response.status_code}: {response.text[:100]}")
                    return []

            # Other errors
            else:
                print(f"   ⚠️  Error {response.status_code}: {response.text[:100]}")
                return []

        except requests.exceptions.Timeout:
            print(f"   ⚠️  Request timeout for {symbol}")
            if retry_count < 2:
                time.sleep(2)
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

    def run_download(self, currency='ETH', start_from=0):
        """
        Main download logic

        Args:
            currency: Currency to download (default ETH)
            start_from: Index to start from (for resuming interrupted downloads)
        """
        print("=" * 80)
        print("CRYPTODATADOWNLOAD HISTORICAL OPTIONS DOWNLOADER V2")
        print("=" * 80)
        print(f"Currency: {currency}")
        print(f"Data granularity: Daily OHLCV")
        print(f"Rate limit: {RATE_LIMIT_DELAY}s between requests")
        print(f"Max retries: {MAX_RETRIES}")
        print("=" * 80)

        self.connect_db()

        # Get list of available options
        options = self.get_available_options(currency)

        if not options:
            print("❌ No options found")
            return

        print(f"\n🎯 Download Plan:")
        print(f"   Total {currency} options: {len(options)}")
        if start_from > 0:
            print(f"   Resuming from index: {start_from}")
        print(f"   Estimated time: ~{(len(options) - start_from) * RATE_LIMIT_DELAY / 60:.1f} minutes")

        # Download data for each option
        print(f"\n" + "=" * 80)
        print(f"DOWNLOADING DAILY DATA")
        print("=" * 80)

        for i, symbol in enumerate(options[start_from:], start=start_from):
            print(f"\n[{i+1}/{len(options)}] {symbol}")
            print(f"   Progress: {(i+1)/len(options)*100:.1f}% | Requests: {self.requests_made} | Records: {self.records_inserted} | Rate limits: {self.rate_limit_hits}")

            # Download data
            data = self.download_ohlcv(symbol)

            if len(data) > 0:
                inserted = self.insert_data(symbol, data)
                print(f"   ✅ Downloaded {len(data)} days, inserted {inserted} records")
                self.symbols_processed += 1
            else:
                print(f"   ⚠️  No data available")

            # Rate limit delay (only if not the last symbol)
            if i < len(options) - 1:
                time.sleep(RATE_LIMIT_DELAY)

        # Final summary
        print(f"\n" + "=" * 80)
        print("DOWNLOAD COMPLETE!")
        print("=" * 80)
        print(f"📊 Statistics:")
        print(f"   Symbols processed: {self.symbols_processed}/{len(options)}")
        print(f"   API requests made: {self.requests_made}")
        print(f"   Daily records inserted: {self.records_inserted}")
        print(f"   Rate limit hits: {self.rate_limit_hits}")
        print(f"   Average days per option: {self.records_inserted/max(self.symbols_processed,1):.1f}")
        print("=" * 80)

        # Close connection
        self.db_conn.close()


def main():
    import sys

    downloader = CryptoDataDownloadDownloader()

    # Allow resuming from a specific index
    start_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    # Download ETH options (user requested)
    downloader.run_download(currency='ETH', start_from=start_index)


if __name__ == "__main__":
    main()
