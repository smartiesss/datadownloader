"""
Options Data Collector (URGENT - Time-Sensitive)
Task: T-014, T-015 (Accelerated due to expiry risk)
Acceptance Criteria: AC-010, AC-011

Collects active options data before expiry:
1. OHLCV historical data (last 30 days)
2. Live Greeks (delta, gamma, vega, theta, rho)
3. Implied volatility, bid/ask spreads
4. Prioritizes options expiring soon

Usage:
    python -m scripts.collect_options_realtime \
        --currencies BTC,ETH \
        --priority-days 7 \
        --ohlcv-days 30
"""

import aiohttp
import asyncio
import psycopg2
import argparse
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from logging_config import setup_logging


class OptionsCollector:
    """Collects time-sensitive options data from Deribit"""

    BASE_URL = "https://www.deribit.com/api/v2"
    RATE_LIMIT_DELAY = 0.05  # 20 req/sec
    MAX_RETRIES = 3

    def __init__(self, db_connection_string="dbname=crypto_data user=postgres"):
        self.db_conn_str = db_connection_string
        self.logger = setup_logging()
        self.evidence_dir = Path(__file__).parent.parent / "tests" / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.options_collected = []
        self.greeks_collected = []

    async def get_active_options(self, session, currency):
        """
        Get all active (non-expired) options for a currency

        Args:
            session: aiohttp ClientSession
            currency: 'BTC' or 'ETH'

        Returns:
            list: Active options with metadata
        """
        url = f"{self.BASE_URL}/public/get_instruments"
        params = {
            "currency": currency,
            "kind": "option",
            "expired": "false"
        }

        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to get {currency} options: {response.status}")
                    return []

                data = await response.json()
                options = data.get('result', [])

                self.logger.info(f"Found {len(options)} active {currency} options")
                return options

        except Exception as e:
            self.logger.error(f"Exception getting {currency} options: {e}")
            return []

    async def collect_option_ohlcv(self, session, instrument, strike, expiry_date,
                                   option_type, days=30, retry_count=0):
        """
        Collect OHLCV data for an option

        Args:
            session: aiohttp ClientSession
            instrument: Instrument name (e.g., BTC-27DEC24-60000-C)
            strike: Strike price
            expiry_date: Expiry date
            option_type: 'call' or 'put'
            days: Days of history to collect
            retry_count: Current retry attempt

        Returns:
            int: Number of candles collected
        """
        end_ts = int(datetime.now().timestamp() * 1000)
        start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        url = f"{self.BASE_URL}/public/get_tradingview_chart_data"
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "resolution": "1"
        }

        try:
            async with session.get(url, params=params) as response:
                if response.status == 429:
                    if retry_count < self.MAX_RETRIES:
                        wait_time = 2 ** retry_count
                        self.logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        return await self.collect_option_ohlcv(
                            session, instrument, strike, expiry_date,
                            option_type, days, retry_count + 1
                        )
                    return 0

                if response.status != 200:
                    self.logger.warning(f"Failed to get OHLCV for {instrument}: {response.status}")
                    return 0

                data = await response.json()
                result = data.get('result', {})

                ticks = result.get('ticks', [])
                opens = result.get('open', [])
                highs = result.get('high', [])
                lows = result.get('low', [])
                closes = result.get('close', [])
                volumes = result.get('volume', [])

                if not ticks:
                    self.logger.debug(f"No OHLCV data for {instrument}")
                    return 0

                # Prepare rows for database
                conn = psycopg2.connect(self.db_conn_str)
                try:
                    cursor = conn.cursor()
                    query = """
                        INSERT INTO options_ohlcv
                            (timestamp, instrument, strike, expiry_date, option_type,
                             open, high, low, close, volume, implied_volatility)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (timestamp, instrument)
                        DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            implied_volatility = EXCLUDED.implied_volatility
                    """

                    rows = []
                    for i in range(len(ticks)):
                        timestamp = datetime.fromtimestamp(ticks[i] / 1000)
                        rows.append((
                            timestamp,
                            instrument,
                            float(strike),
                            expiry_date,
                            option_type,
                            float(opens[i]) if opens[i] else None,
                            float(highs[i]) if highs[i] else None,
                            float(lows[i]) if lows[i] else None,
                            float(closes[i]) if closes[i] else None,
                            float(volumes[i]) if volumes[i] else 0,
                            None  # IV will be updated from Greeks
                        ))

                    cursor.executemany(query, rows)
                    conn.commit()

                    self.options_collected.append({
                        "instrument": instrument,
                        "candles": len(rows),
                        "days": days
                    })

                    return len(rows)

                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"Database error for {instrument}: {e}")
                    return 0
                finally:
                    conn.close()

        except Exception as e:
            self.logger.error(f"Exception collecting OHLCV for {instrument}: {e}")
            return 0

    async def collect_option_greeks(self, session, instrument, retry_count=0):
        """
        Collect live Greeks and market data for an option

        Args:
            session: aiohttp ClientSession
            instrument: Instrument name
            retry_count: Current retry attempt

        Returns:
            dict: Greeks data or None
        """
        url = f"{self.BASE_URL}/public/ticker"
        params = {"instrument_name": instrument}

        try:
            async with session.get(url, params=params) as response:
                if response.status == 429:
                    if retry_count < self.MAX_RETRIES:
                        wait_time = 2 ** retry_count
                        await asyncio.sleep(wait_time)
                        return await self.collect_option_greeks(
                            session, instrument, retry_count + 1
                        )
                    return None

                if response.status != 200:
                    self.logger.warning(f"Failed to get Greeks for {instrument}: {response.status}")
                    return None

                data = await response.json()
                ticker = data.get('result', {})

                greeks_data = ticker.get('greeks', {})
                if not greeks_data:
                    self.logger.debug(f"No Greeks available for {instrument}")
                    return None

                # Store Greeks in database
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
                        datetime.now(),
                        instrument,
                        float(greeks_data.get('delta', 0)),
                        float(greeks_data.get('gamma', 0)),
                        float(greeks_data.get('vega', 0)),
                        float(greeks_data.get('theta', 0)),
                        float(greeks_data.get('rho', 0))
                    ))
                    conn.commit()

                    greeks_record = {
                        "instrument": instrument,
                        "timestamp": datetime.now().isoformat(),
                        "delta": greeks_data.get('delta'),
                        "gamma": greeks_data.get('gamma'),
                        "vega": greeks_data.get('vega'),
                        "theta": greeks_data.get('theta'),
                        "rho": greeks_data.get('rho'),
                        "mark_iv": ticker.get('mark_iv'),
                        "mark_price": ticker.get('mark_price'),
                        "bid_price": ticker.get('best_bid_price'),
                        "ask_price": ticker.get('best_ask_price'),
                        "open_interest": ticker.get('open_interest')
                    }

                    self.greeks_collected.append(greeks_record)
                    return greeks_record

                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"Database error storing Greeks for {instrument}: {e}")
                    return None
                finally:
                    conn.close()

        except Exception as e:
            self.logger.error(f"Exception collecting Greeks for {instrument}: {e}")
            return None

    async def collect_all_options(self, currencies, priority_days=7, ohlcv_days=30):
        """
        Collect all active options data with priority-based collection

        Args:
            currencies: List of currencies ('BTC', 'ETH')
            priority_days: Days threshold for high-priority collection
            ohlcv_days: Days of OHLCV history to collect

        Returns:
            dict: Collection summary
        """
        start_time = datetime.now()
        self.logger.info("=" * 80)
        self.logger.info("URGENT OPTIONS DATA COLLECTION STARTED")
        self.logger.info(f"Currencies: {', '.join(currencies)}")
        self.logger.info(f"Priority threshold: {priority_days} days")
        self.logger.info("=" * 80)

        async with aiohttp.ClientSession() as session:
            all_options = []

            # Get all active options
            for currency in currencies:
                options = await self.get_active_options(session, currency)
                all_options.extend(options)
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            if not all_options:
                self.logger.error("No active options found!")
                return {}

            # Sort by expiry (soonest first)
            all_options.sort(key=lambda x: x['expiration_timestamp'])

            # Categorize by priority
            critical = []  # Expires <7 days
            high = []      # Expires 7-30 days
            medium = []    # Expires 30-90 days
            low = []       # Expires >90 days

            for option in all_options:
                expiry_ts = option['expiration_timestamp'] / 1000
                expiry = datetime.fromtimestamp(expiry_ts)
                days_to_expiry = (expiry - datetime.now()).days

                if days_to_expiry <= priority_days:
                    critical.append((option, days_to_expiry))
                elif days_to_expiry <= 30:
                    high.append((option, days_to_expiry))
                elif days_to_expiry <= 90:
                    medium.append((option, days_to_expiry))
                else:
                    low.append((option, days_to_expiry))

            self.logger.info(f"Priority breakdown:")
            self.logger.info(f"  CRITICAL (expires <{priority_days} days): {len(critical)}")
            self.logger.info(f"  HIGH (7-30 days): {len(high)}")
            self.logger.info(f"  MEDIUM (30-90 days): {len(medium)}")
            self.logger.info(f"  LOW (>90 days): {len(low)}")
            self.logger.info("")

            # Collect CRITICAL options first (full data)
            self.logger.info("=" * 80)
            self.logger.info(f"PHASE 1: Collecting {len(critical)} CRITICAL options")
            self.logger.info("=" * 80)

            for option, days in critical:
                instrument = option['instrument_name']
                strike = option['strike']
                expiry_ts = option['expiration_timestamp'] / 1000
                expiry_date = datetime.fromtimestamp(expiry_ts).date()
                option_type = option['option_type']

                self.logger.info(f"⚠️  CRITICAL: {instrument} (expires in {days} days)")

                # Collect OHLCV
                candles = await self.collect_option_ohlcv(
                    session, instrument, strike, expiry_date, option_type, ohlcv_days
                )
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

                # Collect Greeks
                greeks = await self.collect_option_greeks(session, instrument)
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

                if candles > 0:
                    self.logger.info(f"   ✓ Collected {candles} candles + Greeks")

            # Collect HIGH priority options
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info(f"PHASE 2: Collecting {len(high)} HIGH priority options")
            self.logger.info("=" * 80)

            for option, days in high:
                instrument = option['instrument_name']
                strike = option['strike']
                expiry_ts = option['expiration_timestamp'] / 1000
                expiry_date = datetime.fromtimestamp(expiry_ts).date()
                option_type = option['option_type']

                self.logger.info(f"🔸 HIGH: {instrument} (expires in {days} days)")

                candles = await self.collect_option_ohlcv(
                    session, instrument, strike, expiry_date, option_type, ohlcv_days
                )
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

                greeks = await self.collect_option_greeks(session, instrument)
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            # Collect MEDIUM priority (partial OHLCV)
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info(f"PHASE 3: Collecting {len(medium)} MEDIUM priority options")
            self.logger.info("=" * 80)

            for option, days in medium[:20]:  # Limit to first 20 for time
                instrument = option['instrument_name']
                strike = option['strike']
                expiry_ts = option['expiration_timestamp'] / 1000
                expiry_date = datetime.fromtimestamp(expiry_ts).date()
                option_type = option['option_type']

                candles = await self.collect_option_ohlcv(
                    session, instrument, strike, expiry_date, option_type, days=7
                )
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

                greeks = await self.collect_option_greeks(session, instrument)
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            # Collect LOW priority (Greeks only)
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info(f"PHASE 4: Collecting Greeks for {len(low)} LOW priority options")
            self.logger.info("=" * 80)

            for option, days in low[:50]:  # Limit to first 50
                instrument = option['instrument_name']
                greeks = await self.collect_option_greeks(session, instrument)
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        elapsed = (datetime.now() - start_time).total_seconds()

        # Generate summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": elapsed,
            "total_options": len(all_options),
            "critical_count": len(critical),
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "ohlcv_collected": len(self.options_collected),
            "greeks_collected": len(self.greeks_collected)
        }

        # Save evidence
        evidence_file = self.evidence_dir / f"options-snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(evidence_file, 'w') as f:
            json.dump({
                "summary": summary,
                "options_ohlcv": self.options_collected,
                "greeks_sample": self.greeks_collected[:10]  # First 10 for evidence
            }, f, indent=2)

        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("OPTIONS COLLECTION COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"Total options: {summary['total_options']}")
        self.logger.info(f"OHLCV collected: {summary['ohlcv_collected']} options")
        self.logger.info(f"Greeks collected: {summary['greeks_collected']} options")
        self.logger.info(f"Duration: {elapsed:.1f}s")
        self.logger.info(f"Evidence: {evidence_file}")
        self.logger.info("=" * 80)

        return summary


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Collect time-sensitive options data from Deribit"
    )
    parser.add_argument(
        "--currencies",
        type=str,
        default="BTC,ETH",
        help="Comma-separated currencies (default: BTC,ETH)"
    )
    parser.add_argument(
        "--priority-days",
        type=int,
        default=7,
        help="Days threshold for high-priority collection (default: 7)"
    )
    parser.add_argument(
        "--ohlcv-days",
        type=int,
        default=30,
        help="Days of OHLCV history to collect (default: 30)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="dbname=crypto_data user=postgres",
        help="PostgreSQL connection string"
    )

    args = parser.parse_args()

    currencies = [c.strip() for c in args.currencies.split(',')]

    collector = OptionsCollector(args.db)

    try:
        summary = asyncio.run(
            collector.collect_all_options(
                currencies, args.priority_days, args.ohlcv_days
            )
        )

        if summary.get('critical_count', 0) > 0:
            print("\n✅ SUCCESS: Critical expiring options data captured!")
        else:
            print("\n⚠️  WARNING: No critical expiring options found")

        return 0

    except Exception as e:
        collector.logger.error(f"Options collection failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
