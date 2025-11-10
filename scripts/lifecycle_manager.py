"""
Options Lifecycle Manager

Automatically manages the lifecycle of options instruments:
1. Detects expiring options (within 5 minutes)
2. Detects newly listed options
3. Sends subscribe/unsubscribe commands to collectors via HTTP API
4. Maintains instrument_metadata table
5. Logs all lifecycle events

Usage:
    CURRENCY=BTC python -m scripts.lifecycle_manager
    CURRENCY=ETH python -m scripts.lifecycle_manager
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set, Optional
import aiohttp
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
CURRENCY = os.getenv('CURRENCY', 'BTC').upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/lifecycle_manager_{CURRENCY.lower()}.log')
    ]
)
logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    Manages the lifecycle of options instruments across multiple collectors.
    """

    def __init__(
        self,
        database_url: str,
        currency: str,
        collector_endpoints: List[str],
        refresh_interval_sec: int = 300,
        expiry_buffer_minutes: int = 5
    ):
        """
        Initialize lifecycle manager.

        Args:
            database_url: PostgreSQL connection string
            currency: 'BTC' or 'ETH'
            collector_endpoints: List of collector HTTP API endpoints (e.g., ['http://localhost:8000', ...])
            refresh_interval_sec: How often to check for changes (default 300 = 5 minutes)
            expiry_buffer_minutes: Unsubscribe N minutes before expiry (default 5)
        """
        self.database_url = database_url
        self.currency = currency.upper()
        self.collector_endpoints = collector_endpoints
        self.refresh_interval_sec = refresh_interval_sec
        self.expiry_buffer_minutes = expiry_buffer_minutes

        # State
        self.db_pool: Optional[asyncpg.Pool] = None
        self.running = False
        self.deribit_api_url = "https://www.deribit.com/api/v2"

        # Statistics
        self.stats = {
            'refresh_cycles': 0,
            'instruments_tracked': 0,
            'instruments_expired': 0,
            'instruments_listed': 0,
            'subscriptions_added': 0,
            'subscriptions_removed': 0,
            'errors': 0
        }

        logger.info(
            f"LifecycleManager initialized for {self.currency}: "
            f"refresh_interval={refresh_interval_sec}s, "
            f"expiry_buffer={expiry_buffer_minutes}min, "
            f"collectors={len(collector_endpoints)}"
        )

    async def start(self):
        """Start the lifecycle manager."""
        logger.info(f"Starting lifecycle manager for {self.currency}...")

        try:
            # Connect to database
            self.db_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created")

            # Initial sync
            logger.info("Performing initial instrument sync...")
            await self._sync_instruments()

            # Set running flag
            self.running = True

            # Start refresh loop
            await self._refresh_loop()

        except Exception as e:
            logger.error(f"Fatal error in lifecycle manager: {e}", exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the lifecycle manager gracefully."""
        logger.info("Stopping lifecycle manager...")
        self.running = False

        if self.db_pool:
            await self.db_pool.close()

        logger.info("Lifecycle manager stopped")

    async def _refresh_loop(self):
        """Main refresh loop - runs every refresh_interval_sec."""
        while self.running:
            try:
                await asyncio.sleep(self.refresh_interval_sec)

                if not self.running:
                    break

                self.stats['refresh_cycles'] += 1
                logger.info(f"=== Refresh cycle {self.stats['refresh_cycles']} starting ===")

                await self._sync_instruments()

                logger.info(
                    f"=== Refresh cycle {self.stats['refresh_cycles']} complete | "
                    f"Tracked: {self.stats['instruments_tracked']} | "
                    f"Expired: {self.stats['instruments_expired']} | "
                    f"Listed: {self.stats['instruments_listed']} ==="
                )

            except Exception as e:
                logger.error(f"Error in refresh loop: {e}", exc_info=True)
                self.stats['errors'] += 1

    async def _sync_instruments(self):
        """
        Main sync logic:
        1. Fetch active instruments from Deribit API
        2. Detect expired instruments (in DB but not active on exchange)
        3. Detect new instruments (active on exchange but not in DB)
        4. Update collectors (unsubscribe expired, subscribe new)
        5. Update database (instrument_metadata, lifecycle_events)
        """
        try:
            # Step 1: Fetch active instruments from Deribit API
            logger.info(f"Fetching active {self.currency} options from Deribit...")
            active_instruments = await self._fetch_active_instruments()
            logger.info(f"Found {len(active_instruments)} active options on exchange")

            # Step 2: Get currently tracked instruments from database
            tracked_instruments = await self._get_tracked_instruments()
            logger.info(f"Currently tracking {len(tracked_instruments)} instruments in database")

            # Step 3: Detect changes
            active_set = set(inst['instrument_name'] for inst in active_instruments)
            tracked_set = set(tracked_instruments.keys())

            # Instruments that expired (in DB but not active on exchange)
            expired_instruments = tracked_set - active_set

            # Instruments that are newly listed (active on exchange but not in DB)
            new_instruments = active_set - tracked_set

            logger.info(
                f"Changes detected: {len(expired_instruments)} expired, {len(new_instruments)} newly listed"
            )

            # Step 4: Handle expired instruments
            if expired_instruments:
                await self._handle_expired_instruments(list(expired_instruments))

            # Step 5: Handle new instruments
            if new_instruments:
                # Get full instrument details for new instruments
                new_instrument_details = [
                    inst for inst in active_instruments
                    if inst['instrument_name'] in new_instruments
                ]
                await self._handle_new_instruments(new_instrument_details)

            # Step 6: Update last_seen_at for all active instruments
            await self._update_last_seen(list(active_set))

            # Step 7: Update statistics
            self.stats['instruments_tracked'] = len(active_set)

        except Exception as e:
            logger.error(f"Error in sync_instruments: {e}", exc_info=True)
            self.stats['errors'] += 1
            raise

    async def _fetch_active_instruments(self) -> List[Dict]:
        """
        Fetch all active options from Deribit API, filtering out expiring soon.

        Returns:
            List of instrument dicts with 'instrument_name', 'expiration_timestamp', etc.
        """
        url = f"{self.deribit_api_url}/public/get_instruments"
        params = {
            'currency': self.currency,
            'kind': 'option'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"Deribit API error: {response.status}")

                data = await response.json()

                if 'result' not in data:
                    raise Exception(f"Invalid Deribit API response: {data}")

                instruments = data['result']

                # Filter only active instruments not expiring soon
                now = datetime.now(timezone.utc)
                buffer = timedelta(minutes=self.expiry_buffer_minutes)

                active_instruments = []
                for inst in instruments:
                    # Check if active
                    if not inst.get('is_active', True):
                        continue

                    # Check if expiring soon
                    expiry_ts = inst.get('expiration_timestamp')
                    if expiry_ts:
                        expiry_time = datetime.fromtimestamp(expiry_ts / 1000, tz=timezone.utc)
                        if expiry_time <= now + buffer:
                            logger.debug(f"Skipping {inst['instrument_name']} - expires in {(expiry_time - now).total_seconds()/60:.1f} minutes")
                            continue

                    active_instruments.append(inst)

                return active_instruments

    async def _get_tracked_instruments(self) -> Dict[str, Dict]:
        """
        Get currently tracked instruments from database.

        Returns:
            Dict mapping instrument_name -> row dict
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT instrument_name, is_active, expiry_date, expired_at, last_seen_at
                FROM instrument_metadata
                WHERE currency = $1 AND is_active = TRUE
                """,
                self.currency
            )

            return {row['instrument_name']: dict(row) for row in rows}

    async def _handle_expired_instruments(self, expired_instruments: List[str]):
        """
        Handle instruments that have expired:
        1. Mark as inactive in database
        2. Send unsubscribe command to collectors
        3. Log lifecycle events
        """
        logger.info(f"Handling {len(expired_instruments)} expired instruments...")

        for instrument in expired_instruments:
            try:
                # Mark as inactive in database
                await self._mark_instrument_expired(instrument)

                # Send unsubscribe to all collectors
                success = await self._unsubscribe_from_collectors(instrument)

                # Log lifecycle event
                await self._log_lifecycle_event(
                    event_type='instrument_expired',
                    instrument_name=instrument,
                    success=success,
                    details={'expired_at': datetime.now(timezone.utc).isoformat()}
                )

                self.stats['instruments_expired'] += 1
                logger.info(f"✅ Expired instrument handled: {instrument}")

            except Exception as e:
                logger.error(f"Failed to handle expired instrument {instrument}: {e}")
                self.stats['errors'] += 1

                # Log failure
                await self._log_lifecycle_event(
                    event_type='instrument_expired',
                    instrument_name=instrument,
                    success=False,
                    error_message=str(e)
                )

    async def _handle_new_instruments(self, new_instruments: List[Dict]):
        """
        Handle newly listed instruments:
        1. Add to database with metadata
        2. Send subscribe command to collectors
        3. Log lifecycle events
        """
        logger.info(f"Handling {len(new_instruments)} newly listed instruments...")

        for inst_details in new_instruments:
            instrument_name = inst_details['instrument_name']

            try:
                # Extract metadata
                metadata = self._extract_instrument_metadata(inst_details)

                # Add to database
                await self._add_instrument_to_db(instrument_name, metadata)

                # Send subscribe to all collectors
                success = await self._subscribe_to_collectors(instrument_name)

                # Log lifecycle event
                await self._log_lifecycle_event(
                    event_type='instrument_listed',
                    instrument_name=instrument_name,
                    success=success,
                    details=metadata
                )

                self.stats['instruments_listed'] += 1
                logger.info(f"✅ New instrument listed: {instrument_name}")

            except Exception as e:
                logger.error(f"Failed to handle new instrument {instrument_name}: {e}")
                self.stats['errors'] += 1

                # Log failure
                await self._log_lifecycle_event(
                    event_type='instrument_listed',
                    instrument_name=instrument_name,
                    success=False,
                    error_message=str(e)
                )

    def _extract_instrument_metadata(self, inst_details: Dict) -> Dict:
        """Extract metadata from Deribit instrument response."""
        expiry_ts = inst_details.get('expiration_timestamp')
        expiry_date = datetime.fromtimestamp(expiry_ts / 1000, tz=timezone.utc) if expiry_ts else None

        return {
            'instrument_type': inst_details.get('kind', 'option'),
            'strike_price': inst_details.get('strike'),
            'expiry_date': expiry_date,
            'option_type': inst_details.get('option_type')  # 'call' or 'put'
        }

    async def _mark_instrument_expired(self, instrument_name: str):
        """Mark instrument as expired in database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE instrument_metadata
                SET is_active = FALSE, expired_at = NOW(), updated_at = NOW()
                WHERE instrument_name = $1 AND currency = $2
                """,
                instrument_name,
                self.currency
            )
            logger.debug(f"Marked {instrument_name} as expired in database")

    async def _add_instrument_to_db(self, instrument_name: str, metadata: Dict):
        """Add new instrument to database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO instrument_metadata
                (instrument_name, currency, instrument_type, strike_price, expiry_date, option_type, is_active, listed_at, last_seen_at)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE, NOW(), NOW())
                ON CONFLICT (instrument_name) DO UPDATE SET
                    is_active = TRUE,
                    last_seen_at = NOW(),
                    updated_at = NOW()
                """,
                instrument_name,
                self.currency,
                metadata.get('instrument_type', 'option'),
                metadata.get('strike_price'),
                metadata.get('expiry_date'),
                metadata.get('option_type')
            )
            logger.debug(f"Added {instrument_name} to database")

    async def _update_last_seen(self, instrument_names: List[str]):
        """Update last_seen_at timestamp for active instruments."""
        if not instrument_names:
            return

        async with self.db_pool.acquire() as conn:
            # Use unnest for efficient batch update
            await conn.execute(
                """
                UPDATE instrument_metadata
                SET last_seen_at = NOW(), updated_at = NOW()
                WHERE instrument_name = ANY($1::text[]) AND currency = $2
                """,
                instrument_names,
                self.currency
            )
            logger.debug(f"Updated last_seen_at for {len(instrument_names)} instruments")

    async def _subscribe_to_collectors(self, instrument_name: str) -> bool:
        """
        Send subscribe command to all collectors.

        Returns:
            True if all collectors succeeded, False otherwise
        """
        success_count = 0

        async with aiohttp.ClientSession() as session:
            for collector_url in self.collector_endpoints:
                try:
                    url = f"{collector_url}/api/subscribe"
                    payload = {
                        'instruments': [instrument_name]
                    }

                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            success_count += 1
                            logger.debug(f"Subscribed {instrument_name} to {collector_url}")
                        else:
                            logger.error(f"Failed to subscribe {instrument_name} to {collector_url}: {response.status}")

                            # Log event
                            await self._log_lifecycle_event(
                                event_type='subscription_added',
                                instrument_name=instrument_name,
                                collector_id=collector_url,
                                success=False,
                                error_message=f"HTTP {response.status}"
                            )

                except Exception as e:
                    logger.error(f"Exception subscribing {instrument_name} to {collector_url}: {e}")

                    # Log event
                    await self._log_lifecycle_event(
                        event_type='subscription_added',
                        instrument_name=instrument_name,
                        collector_id=collector_url,
                        success=False,
                        error_message=str(e)
                    )

        # Log successful subscriptions
        if success_count > 0:
            await self._log_lifecycle_event(
                event_type='subscription_added',
                instrument_name=instrument_name,
                success=True,
                details={'collectors_count': success_count}
            )
            self.stats['subscriptions_added'] += 1

        return success_count == len(self.collector_endpoints)

    async def _unsubscribe_from_collectors(self, instrument_name: str) -> bool:
        """
        Send unsubscribe command to all collectors.

        Returns:
            True if all collectors succeeded, False otherwise
        """
        success_count = 0

        async with aiohttp.ClientSession() as session:
            for collector_url in self.collector_endpoints:
                try:
                    url = f"{collector_url}/api/unsubscribe"
                    payload = {
                        'instruments': [instrument_name]
                    }

                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            success_count += 1
                            logger.debug(f"Unsubscribed {instrument_name} from {collector_url}")
                        else:
                            logger.error(f"Failed to unsubscribe {instrument_name} from {collector_url}: {response.status}")

                            # Log event
                            await self._log_lifecycle_event(
                                event_type='subscription_removed',
                                instrument_name=instrument_name,
                                collector_id=collector_url,
                                success=False,
                                error_message=f"HTTP {response.status}"
                            )

                except Exception as e:
                    logger.error(f"Exception unsubscribing {instrument_name} from {collector_url}: {e}")

                    # Log event
                    await self._log_lifecycle_event(
                        event_type='subscription_removed',
                        instrument_name=instrument_name,
                        collector_id=collector_url,
                        success=False,
                        error_message=str(e)
                    )

        # Log successful unsubscriptions
        if success_count > 0:
            await self._log_lifecycle_event(
                event_type='subscription_removed',
                instrument_name=instrument_name,
                success=True,
                details={'collectors_count': success_count}
            )
            self.stats['subscriptions_removed'] += 1

        return success_count == len(self.collector_endpoints)

    async def _log_lifecycle_event(
        self,
        event_type: str,
        instrument_name: Optional[str] = None,
        collector_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """Log lifecycle event to database."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO lifecycle_events
                    (event_type, instrument_name, currency, collector_id, details, success, error_message)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    event_type,
                    instrument_name,
                    self.currency,
                    collector_id,
                    json.dumps(details) if details else None,
                    success,
                    error_message
                )
        except Exception as e:
            logger.error(f"Failed to log lifecycle event: {e}")


async def main():
    """Main entry point for lifecycle manager."""
    logger.info(f"Starting lifecycle manager for {CURRENCY}...")

    # Load configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')
    REFRESH_INTERVAL_SEC = int(os.getenv('LIFECYCLE_REFRESH_INTERVAL_SEC', 300))  # 5 minutes
    EXPIRY_BUFFER_MINUTES = int(os.getenv('LIFECYCLE_EXPIRY_BUFFER_MINUTES', 5))

    # Parse collector endpoints from environment
    # Format: COLLECTOR_ENDPOINTS=http://btc-options-0:8000,http://btc-options-1:8000,http://btc-options-2:8000
    collector_endpoints_str = os.getenv('COLLECTOR_ENDPOINTS', '')
    if not collector_endpoints_str:
        logger.error("COLLECTOR_ENDPOINTS environment variable not set")
        sys.exit(1)

    collector_endpoints = [url.strip() for url in collector_endpoints_str.split(',') if url.strip()]
    if not collector_endpoints:
        logger.error("No valid collector endpoints found in COLLECTOR_ENDPOINTS")
        sys.exit(1)

    logger.info(f"Collector endpoints: {collector_endpoints}")

    # Create lifecycle manager
    manager = LifecycleManager(
        database_url=DATABASE_URL,
        currency=CURRENCY,
        collector_endpoints=collector_endpoints,
        refresh_interval_sec=REFRESH_INTERVAL_SEC,
        expiry_buffer_minutes=EXPIRY_BUFFER_MINUTES
    )

    # Start manager
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await manager.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await manager.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    # Run lifecycle manager
    asyncio.run(main())
