"""
Real-Time Data Collector - Continuous Updates
Task: Phase 4 - Continuous Collection
Acceptance Criteria: AC-016, AC-017, AC-018

Continuously collects and updates all instruments:
- Perpetuals OHLCV (every 1 minute)
- Futures OHLCV (every 1 minute, active contracts)
- Options OHLCV (every 1 minute, active contracts)
- Options Greeks (every 1 hour)
- Funding rates (every 8 hours)

Usage:
    # Run continuously (press Ctrl+C to stop)
    python -m scripts.collect_realtime

    # Run as daemon with nohup
    nohup python -m scripts.collect_realtime > logs/realtime.log 2>&1 &
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


class RealtimeCollector:
    """Continuous real-time data collector for all instruments"""

    BASE_URL = "https://www.deribit.com/api/v2/public"
    RATE_LIMIT_DELAY = 0.025  # 40 req/sec - testing faster collection

    # Collection intervals
    PERPETUAL_INTERVAL = 60  # 1 minute
    FUTURES_INTERVAL = 60    # 1 minute
    OPTIONS_OHLCV_INTERVAL = 60  # 1 minute
    OPTIONS_GREEKS_INTERVAL = 3600  # 1 hour
    FUNDING_INTERVAL = 28800  # 8 hours

    # Instrument refresh interval
    INSTRUMENTS_REFRESH = 3600  # Refresh list every hour

    def __init__(self, db_connection_string="dbname=crypto_data user=postgres"):
        self.db_conn_str = db_connection_string
        self.logger = setup_logging()
        self.running = True

        # Cached instrument lists
        self.perpetuals = []
        self.futures = []
        self.options = []
        self.last_instruments_fetch = None

        # Last collection timestamps
        self.last_perpetual_collection = None
        self.last_futures_collection = None
        self.last_options_ohlcv_collection = None
        self.last_options_greeks_collection = None
        self.last_funding_collection = None

    async def fetch_instruments(self, currency, kind):
        """Fetch list of instruments from Deribit

        Args:
            currency: BTC or ETH
            kind: future, option, or any

        Returns:
            list: List of instrument names
        """
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
                        self.logger.info(f"Fetched {len(instruments)} {kind}s for {currency}")
                        return instruments
                    else:
                        self.logger.error(f"Failed to fetch instruments: HTTP {response.status}")
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching instruments: {e}")
            return []

    async def refresh_instruments(self):
        """Refresh cached instrument lists"""
        self.logger.info("Refreshing instrument lists...")

        # Perpetuals
        self.perpetuals = ['BTC-PERPETUAL', 'ETH-PERPETUAL']

        # Futures
        btc_futures = await self.fetch_instruments('BTC', 'future')
        eth_futures = await self.fetch_instruments('ETH', 'future')
        self.futures = btc_futures + eth_futures

        # Options
        btc_options = await self.fetch_instruments('BTC', 'option')
        eth_options = await self.fetch_instruments('ETH', 'option')
        self.options = btc_options + eth_options

        self.last_instruments_fetch = datetime.now()
        self.logger.info(
            f"Instruments refreshed: {len(self.perpetuals)} perpetuals, "
            f"{len(self.futures)} futures, {len(self.options)} options"
        )

    async def fetch_latest_candle(self, session, instrument):
        """Fetch the most recent 1-minute candle

        Args:
            session: aiohttp ClientSession
            instrument: Instrument name

        Returns:
            dict: Candle data or None
        """
        # Get last 2 candles to ensure we have the latest completed one
        end_ts = int(datetime.now().timestamp() * 1000)
        start_ts = end_ts - (2 * 60 * 1000)  # 2 minutes ago

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
                    if not ticks:
                        return None

                    # Get the most recent candle
                    idx = -1
                    return {
                        'timestamp': datetime.fromtimestamp(ticks[idx] / 1000),
                        'open': float(result.get('open', [])[idx]),
                        'high': float(result.get('high', [])[idx]),
                        'low': float(result.get('low', [])[idx]),
                        'close': float(result.get('close', [])[idx]),
                        'volume': float(result.get('volume', [])[idx])
                    }
                else:
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching candle for {instrument}: {e}")
            return None

    async def fetch_ticker(self, session, instrument):
        """Fetch complete ticker data including Greeks, bid/ask, and IV

        Args:
            session: aiohttp ClientSession
            instrument: Instrument name

        Returns:
            dict: Complete ticker data or None
        """
        url = f"{self.BASE_URL}/ticker"
        params = {"instrument_name": instrument}

        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    greeks = result.get('greeks', {})

                    # Helper to safely convert to float, handling None values
                    def safe_float(value, default=0.0):
                        if value is None:
                            return default
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return default

                    return {
                        'timestamp': datetime.now(),
                        # Greeks
                        'delta': safe_float(greeks.get('delta')),
                        'gamma': safe_float(greeks.get('gamma')),
                        'vega': safe_float(greeks.get('vega')),
                        'theta': safe_float(greeks.get('theta')),
                        'rho': safe_float(greeks.get('rho')),
                        # Prices
                        'best_bid_price': safe_float(result.get('best_bid_price')),
                        'best_ask_price': safe_float(result.get('best_ask_price')),
                        'mark_price': safe_float(result.get('mark_price')),
                        'last_price': safe_float(result.get('last_price')),
                        # IV
                        'mark_iv': safe_float(result.get('mark_iv')),
                        'bid_iv': safe_float(result.get('bid_iv')),
                        'ask_iv': safe_float(result.get('ask_iv')),
                        # Underlying
                        'underlying_price': safe_float(result.get('underlying_price')),
                        # Volume
                        'volume': safe_float(result.get('stats', {}).get('volume'))
                    }
                else:
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching ticker for {instrument}: {e}")
            return None

    async def fetch_greeks(self, session, instrument):
        """Fetch live Greeks for an option (legacy method, now uses fetch_ticker)

        Args:
            session: aiohttp ClientSession
            instrument: Option instrument name

        Returns:
            dict: Greeks data or None
        """
        ticker = await self.fetch_ticker(session, instrument)
        if ticker:
            return {
                'timestamp': ticker['timestamp'],
                'delta': ticker['delta'],
                'gamma': ticker['gamma'],
                'vega': ticker['vega'],
                'theta': ticker['theta'],
                'rho': ticker['rho']
            }
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
            self.logger.error(f"Error upserting perpetual OHLCV for {instrument}: {e}")
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
            self.logger.error(f"Error upserting futures OHLCV for {instrument}: {e}")
        finally:
            conn.close()

    def upsert_options_ohlcv(self, instrument, ticker_data, strike, expiry_date, option_type):
        """Upsert options OHLCV with bid/ask/IV to database"""
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

            # Use mark_price as close if available, otherwise last_price
            close_price = ticker_data.get('mark_price', ticker_data.get('last_price', 0))

            cursor.execute(query, (
                ticker_data['timestamp'], instrument, strike, expiry_date, option_type,
                close_price, close_price, close_price, close_price,  # open/high/low/close all same for ticker snapshot
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
            # Skip NULL constraint errors for illiquid options
            if "null value" not in str(e).lower():
                self.logger.error(f"Error upserting options OHLCV for {instrument}: {e}")
        finally:
            conn.close()

    def upsert_options_greeks(self, instrument, greeks):
        """Upsert options Greeks to database"""
        conn = psycopg2.connect(self.db_conn_str)
        try:
            cursor = conn.cursor()
            query = """
                INSERT INTO options_greeks
                    (timestamp, instrument, delta, gamma, vega, theta, rho)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, instrument)
                DO UPDATE SET
                    delta = EXCLUDED.delta,
                    gamma = EXCLUDED.gamma,
                    vega = EXCLUDED.vega,
                    theta = EXCLUDED.theta,
                    rho = EXCLUDED.rho
            """
            cursor.execute(query, (
                greeks['timestamp'], instrument,
                greeks['delta'], greeks['gamma'], greeks['vega'],
                greeks['theta'], greeks['rho']
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error upserting Greeks for {instrument}: {e}")
        finally:
            conn.close()

    def parse_instrument(self, instrument_name):
        """Parse instrument name to extract metadata

        Args:
            instrument_name: e.g., BTC-27DEC24, BTC-27DEC24-100000-C

        Returns:
            dict: Parsed metadata
        """
        parts = instrument_name.split('-')

        # Futures: BTC-27DEC24
        if len(parts) == 2:
            return {
                'type': 'future',
                'currency': parts[0],
                'expiry_str': parts[1]
            }

        # Options: BTC-27DEC24-100000-C
        elif len(parts) == 4:
            return {
                'type': 'option',
                'currency': parts[0],
                'expiry_str': parts[1],
                'strike': float(parts[2]),
                'option_type': 'call' if parts[3] == 'C' else 'put'
            }

        return None

    async def collect_perpetuals(self):
        """Collect latest perpetual OHLCV"""
        self.logger.info(f"Collecting perpetuals OHLCV ({len(self.perpetuals)} instruments)...")

        async with aiohttp.ClientSession() as session:
            for instrument in self.perpetuals:
                candle = await self.fetch_latest_candle(session, instrument)
                if candle:
                    self.upsert_perpetual_ohlcv(instrument, candle)
                    self.logger.debug(f"Updated {instrument}: {candle['close']}")

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        self.last_perpetual_collection = datetime.now()
        self.logger.info("Perpetuals collection complete")

    async def collect_futures(self):
        """Collect latest futures OHLCV"""
        # Filter out perpetuals from futures list (perpetuals end with -PERPETUAL)
        actual_futures = [f for f in self.futures if not f.endswith('-PERPETUAL')]
        self.logger.info(f"Collecting futures OHLCV ({len(actual_futures)} instruments)...")

        async with aiohttp.ClientSession() as session:
            for instrument in actual_futures:
                metadata = self.parse_instrument(instrument)
                if not metadata:
                    continue

                candle = await self.fetch_latest_candle(session, instrument)
                if candle:
                    # Parse expiry date from instrument name (e.g., 27DEC24)
                    expiry_str = metadata['expiry_str']
                    try:
                        expiry_date = datetime.strptime(expiry_str, '%d%b%y').date()
                        self.upsert_futures_ohlcv(instrument, candle, expiry_date)
                        self.logger.debug(f"Updated {instrument}: {candle['close']}")
                    except ValueError:
                        self.logger.error(f"Could not parse expiry date from {instrument}")

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        self.last_futures_collection = datetime.now()
        self.logger.info("Futures collection complete")

    async def collect_options_ohlcv(self):
        """Collect latest options OHLCV with bid/ask and IV"""
        self.logger.info(f"Collecting options OHLCV with bid/ask/IV ({len(self.options)} instruments)...")

        async with aiohttp.ClientSession() as session:
            for instrument in self.options:
                metadata = self.parse_instrument(instrument)
                if not metadata:
                    continue

                # Fetch ticker data (includes bid/ask, IV, prices, volume)
                ticker_data = await self.fetch_ticker(session, instrument)
                if ticker_data:
                    try:
                        expiry_str = metadata['expiry_str']
                        expiry_date = datetime.strptime(expiry_str, '%d%b%y').date()
                        self.upsert_options_ohlcv(
                            instrument, ticker_data,
                            metadata['strike'], expiry_date, metadata['option_type']
                        )
                        self.logger.debug(
                            f"Updated {instrument}: mark={ticker_data.get('mark_price', 0):.4f}, "
                            f"bid={ticker_data.get('best_bid_price', 0):.4f}, "
                            f"ask={ticker_data.get('best_ask_price', 0):.4f}, "
                            f"mark_iv={ticker_data.get('mark_iv', 0):.2f}%"
                        )
                    except ValueError:
                        self.logger.error(f"Could not parse expiry date from {instrument}")

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        self.last_options_ohlcv_collection = datetime.now()
        self.logger.info("Options OHLCV collection complete")

    async def collect_options_greeks(self):
        """Collect latest options Greeks"""
        self.logger.info(f"Collecting options Greeks ({len(self.options)} instruments)...")

        async with aiohttp.ClientSession() as session:
            for instrument in self.options:
                greeks = await self.fetch_greeks(session, instrument)
                if greeks:
                    self.upsert_options_greeks(instrument, greeks)
                    self.logger.debug(f"Updated Greeks for {instrument}")

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        self.last_options_greeks_collection = datetime.now()
        self.logger.info("Options Greeks collection complete")

    async def run(self):
        """Main continuous collection loop"""
        self.logger.info("="*80)
        self.logger.info("REAL-TIME DATA COLLECTOR STARTED")
        self.logger.info("="*80)
        self.logger.info("Collection intervals:")
        self.logger.info(f"  Perpetuals OHLCV: every {self.PERPETUAL_INTERVAL}s (1 min)")
        self.logger.info(f"  Futures OHLCV: every {self.FUTURES_INTERVAL}s (1 min)")
        self.logger.info(f"  Options OHLCV: every {self.OPTIONS_OHLCV_INTERVAL}s (1 min)")
        self.logger.info(f"  Options Greeks: every {self.OPTIONS_GREEKS_INTERVAL}s (1 hour)")
        self.logger.info(f"  Instruments refresh: every {self.INSTRUMENTS_REFRESH}s (1 hour)")
        self.logger.info("="*80)

        # Initial instrument fetch
        await self.refresh_instruments()

        try:
            while self.running:
                now = datetime.now()

                # Refresh instruments every hour
                if (not self.last_instruments_fetch or
                    (now - self.last_instruments_fetch).total_seconds() >= self.INSTRUMENTS_REFRESH):
                    await self.refresh_instruments()

                # Collect perpetuals every minute
                if (not self.last_perpetual_collection or
                    (now - self.last_perpetual_collection).total_seconds() >= self.PERPETUAL_INTERVAL):
                    await self.collect_perpetuals()

                # Collect futures every minute
                if (not self.last_futures_collection or
                    (now - self.last_futures_collection).total_seconds() >= self.FUTURES_INTERVAL):
                    await self.collect_futures()

                # Collect options OHLCV every minute
                if (not self.last_options_ohlcv_collection or
                    (now - self.last_options_ohlcv_collection).total_seconds() >= self.OPTIONS_OHLCV_INTERVAL):
                    await self.collect_options_ohlcv()

                # Collect options Greeks every hour
                if (not self.last_options_greeks_collection or
                    (now - self.last_options_greeks_collection).total_seconds() >= self.OPTIONS_GREEKS_INTERVAL):
                    await self.collect_options_greeks()

                # Sleep for a short interval before checking again
                await asyncio.sleep(30)  # Check every 30 seconds

        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal (Ctrl+C)")
            self.running = False
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}")
            raise


def main():
    """Main entry point"""
    collector = RealtimeCollector()

    try:
        asyncio.run(collector.run())
    except KeyboardInterrupt:
        collector.logger.info("Shutdown complete")
        return 0
    except Exception as e:
        collector.logger.error(f"Collector failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
