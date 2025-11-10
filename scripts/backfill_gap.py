"""
Quick Backfill Script for Data Gaps
Fills missing 1-minute candles for all instruments
"""

import aiohttp
import asyncio
import psycopg2
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from logging_config import setup_logging


class GapBackfiller:
    """Backfill missing data for short time gaps"""

    BASE_URL = "https://www.deribit.com/api/v2/public"
    RATE_LIMIT_DELAY = 0.025  # 40 req/sec

    def __init__(self, db_connection_string="dbname=crypto_data user=postgres"):
        self.db_conn_str = db_connection_string
        self.logger = setup_logging()

    async def fetch_candles(self, session, instrument, start_ts, end_ts):
        """Fetch candles for a time range

        Args:
            session: aiohttp ClientSession
            instrument: Instrument name
            start_ts: Start timestamp (milliseconds)
            end_ts: End timestamp (milliseconds)

        Returns:
            list: List of candle dicts
        """
        url = f"{self.BASE_URL}/get_tradingview_chart_data"
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "resolution": 1
        }

        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})

                    ticks = result.get('ticks', [])
                    opens = result.get('open', [])
                    highs = result.get('high', [])
                    lows = result.get('low', [])
                    closes = result.get('close', [])
                    volumes = result.get('volume', [])

                    candles = []
                    for i in range(len(ticks)):
                        candles.append({
                            'timestamp': datetime.fromtimestamp(ticks[i] / 1000),
                            'open': float(opens[i]),
                            'high': float(highs[i]),
                            'low': float(lows[i]),
                            'close': float(closes[i]),
                            'volume': float(volumes[i])
                        })

                    return candles
                else:
                    self.logger.error(f"Failed to fetch candles for {instrument}: HTTP {response.status}")
                    return []
        except Exception as e:
            self.logger.error(f"Error fetching candles for {instrument}: {e}")
            return []

    async def fetch_ticker(self, session, instrument):
        """Fetch complete ticker data for options"""
        url = f"{self.BASE_URL}/ticker"
        params = {"instrument_name": instrument}

        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    greeks = result.get('greeks', {})

                    def safe_float(value, default=0.0):
                        if value is None:
                            return default
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return default

                    return {
                        'delta': safe_float(greeks.get('delta')),
                        'gamma': safe_float(greeks.get('gamma')),
                        'vega': safe_float(greeks.get('vega')),
                        'theta': safe_float(greeks.get('theta')),
                        'rho': safe_float(greeks.get('rho')),
                        'best_bid_price': safe_float(result.get('best_bid_price')),
                        'best_ask_price': safe_float(result.get('best_ask_price')),
                        'mark_price': safe_float(result.get('mark_price')),
                        'last_price': safe_float(result.get('last_price')),
                        'mark_iv': safe_float(result.get('mark_iv')),
                        'bid_iv': safe_float(result.get('bid_iv')),
                        'ask_iv': safe_float(result.get('ask_iv')),
                        'underlying_price': safe_float(result.get('underlying_price')),
                        'volume': safe_float(result.get('stats', {}).get('volume'))
                    }
                else:
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching ticker for {instrument}: {e}")
            return None

    def upsert_perpetual_ohlcv(self, instrument, candle):
        """Upsert perpetual OHLCV to database"""
        conn = psycopg2.connect(self.db_conn_str)
        try:
            cursor = conn.cursor()
            query = """
                INSERT INTO perpetuals_ohlcv
                    (timestamp, instrument, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, instrument)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """
            cursor.execute(query, (
                candle['timestamp'], instrument,
                candle['open'], candle['high'], candle['low'],
                candle['close'], candle['volume']
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error upserting perpetual: {e}")
        finally:
            conn.close()

    def upsert_futures_ohlcv(self, instrument, candle, expiry_date):
        """Upsert futures OHLCV to database"""
        conn = psycopg2.connect(self.db_conn_str)
        try:
            cursor = conn.cursor()
            query = """
                INSERT INTO futures_ohlcv
                    (timestamp, instrument, expiry_date, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, instrument)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """
            cursor.execute(query, (
                candle['timestamp'], instrument, expiry_date,
                candle['open'], candle['high'], candle['low'],
                candle['close'], candle['volume']
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error upserting futures: {e}")
        finally:
            conn.close()

    def upsert_options_ohlcv(self, instrument, timestamp, ticker_data, strike, expiry_date, option_type):
        """Upsert options OHLCV with bid/ask/IV"""
        conn = psycopg2.connect(self.db_conn_str)
        try:
            cursor = conn.cursor()
            query = """
                INSERT INTO options_ohlcv
                    (timestamp, instrument, strike, expiry_date, option_type,
                     open, high, low, close, volume,
                     best_bid_price, best_ask_price, mark_price,
                     mark_iv, bid_iv, ask_iv, underlying_price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, instrument)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    best_bid_price = EXCLUDED.best_bid_price,
                    best_ask_price = EXCLUDED.best_ask_price,
                    mark_price = EXCLUDED.mark_price,
                    mark_iv = EXCLUDED.mark_iv,
                    bid_iv = EXCLUDED.bid_iv,
                    ask_iv = EXCLUDED.ask_iv,
                    underlying_price = EXCLUDED.underlying_price
            """

            close_price = ticker_data.get('mark_price', ticker_data.get('last_price', 0))

            cursor.execute(query, (
                timestamp, instrument, strike, expiry_date, option_type,
                close_price, close_price, close_price, close_price,
                ticker_data.get('volume', 0),
                ticker_data.get('best_bid_price', 0),
                ticker_data.get('best_ask_price', 0),
                ticker_data.get('mark_price', 0),
                ticker_data.get('mark_iv', 0),
                ticker_data.get('bid_iv', 0),
                ticker_data.get('ask_iv', 0),
                ticker_data.get('underlying_price', 0)
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "null value" not in str(e).lower():
                self.logger.error(f"Error upserting options: {e}")
        finally:
            conn.close()

    def parse_instrument(self, instrument_name):
        """Parse instrument name to extract metadata"""
        parts = instrument_name.split('-')

        if len(parts) == 2:
            return {
                'type': 'future',
                'currency': parts[0],
                'expiry_str': parts[1]
            }
        elif len(parts) == 4:
            return {
                'type': 'option',
                'currency': parts[0],
                'expiry_str': parts[1],
                'strike': float(parts[2]),
                'option_type': 'call' if parts[3] == 'C' else 'put'
            }
        return None

    async def fetch_instruments(self, currency, kind):
        """Fetch list of instruments"""
        url = f"{self.BASE_URL}/get_instruments"
        params = {
            "currency": currency,
            "kind": kind,
            "expired": "false"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        instruments = [item['instrument_name'] for item in data.get('result', [])]
                        return instruments
                    else:
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching instruments: {e}")
            return []

    async def backfill_range(self, start_time_str, end_time_str):
        """Backfill data for a specific time range

        Args:
            start_time_str: Start time in format 'YYYY-MM-DD HH:MM:SS'
            end_time_str: End time in format 'YYYY-MM-DD HH:MM:SS'
        """
        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')

        start_ts = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)

        minutes_gap = int((end_time - start_time).total_seconds() / 60)

        self.logger.info("="*80)
        self.logger.info(f"BACKFILLING GAP: {start_time_str} to {end_time_str}")
        self.logger.info(f"Gap duration: {minutes_gap} minutes")
        self.logger.info("="*80)

        # Fetch instrument lists
        self.logger.info("Fetching instrument lists...")
        perpetuals = ['BTC-PERPETUAL', 'ETH-PERPETUAL']
        btc_futures = await self.fetch_instruments('BTC', 'future')
        eth_futures = await self.fetch_instruments('ETH', 'future')
        futures = [f for f in (btc_futures + eth_futures) if not f.endswith('-PERPETUAL')]
        btc_options = await self.fetch_instruments('BTC', 'option')
        eth_options = await self.fetch_instruments('ETH', 'option')
        options = btc_options + eth_options

        self.logger.info(f"Found: {len(perpetuals)} perpetuals, {len(futures)} futures, {len(options)} options")

        # Backfill perpetuals
        self.logger.info("Backfilling perpetuals...")
        async with aiohttp.ClientSession() as session:
            for instrument in perpetuals:
                candles = await self.fetch_candles(session, instrument, start_ts, end_ts)
                for candle in candles:
                    self.upsert_perpetual_ohlcv(instrument, candle)
                self.logger.info(f"  {instrument}: {len(candles)} candles")
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        # Backfill futures
        self.logger.info("Backfilling futures...")
        async with aiohttp.ClientSession() as session:
            for instrument in futures:
                metadata = self.parse_instrument(instrument)
                if not metadata:
                    continue

                candles = await self.fetch_candles(session, instrument, start_ts, end_ts)
                try:
                    expiry_date = datetime.strptime(metadata['expiry_str'], '%d%b%y').date()
                    for candle in candles:
                        self.upsert_futures_ohlcv(instrument, candle, expiry_date)
                    self.logger.info(f"  {instrument}: {len(candles)} candles")
                except ValueError:
                    self.logger.error(f"  Could not parse expiry date from {instrument}")

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        # Backfill options (use current ticker since historical options data not available per-minute)
        self.logger.info("Backfilling options (using current ticker for recent timestamps)...")
        async with aiohttp.ClientSession() as session:
            for instrument in options:
                metadata = self.parse_instrument(instrument)
                if not metadata:
                    continue

                ticker_data = await self.fetch_ticker(session, instrument)
                if ticker_data:
                    try:
                        expiry_date = datetime.strptime(metadata['expiry_str'], '%d%b%y').date()
                        # Insert for each missing minute
                        current = start_time
                        while current <= end_time:
                            self.upsert_options_ohlcv(
                                instrument, current, ticker_data,
                                metadata['strike'], expiry_date, metadata['option_type']
                            )
                            current += timedelta(minutes=1)
                        self.logger.debug(f"  {instrument}: backfilled {minutes_gap} minutes")
                    except ValueError:
                        self.logger.error(f"  Could not parse expiry date from {instrument}")

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        self.logger.info("="*80)
        self.logger.info("BACKFILL COMPLETE")
        self.logger.info("="*80)


async def main():
    """Main entry point"""
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.backfill_gap 'YYYY-MM-DD HH:MM:SS' 'YYYY-MM-DD HH:MM:SS'")
        print("Example: python -m scripts.backfill_gap '2025-10-27 01:55:00' '2025-10-27 02:04:00'")
        return 1

    start_time = sys.argv[1]
    end_time = sys.argv[2]

    backfiller = GapBackfiller()
    await backfiller.backfill_range(start_time, end_time)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
