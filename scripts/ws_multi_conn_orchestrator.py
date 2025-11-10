"""
Multi-Connection WebSocket Orchestrator
Fetches ALL options and partitions them across multiple WebSocket connections.

This orchestrator:
1. Fetches ALL active options for a currency (not just top N)
2. Partitions instruments into groups of ≤250 (500 channels max per connection)
3. Each partition is handled by a separate WebSocket collector instance

Usage:
    CURRENCY=BTC CONNECTION_ID=0 python -m scripts.ws_multi_conn_orchestrator
    CURRENCY=BTC CONNECTION_ID=1 python -m scripts.ws_multi_conn_orchestrator
    ...
"""

import asyncio
import json
import logging
import os
import sys
from typing import List, Dict, Optional
from datetime import datetime
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
CURRENCY = os.getenv('CURRENCY', 'ETH').upper()
CONNECTION_ID = int(os.getenv('CONNECTION_ID', '0'))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/ws_multi_conn_{CURRENCY.lower()}_{CONNECTION_ID}.log')
    ]
)
logger = logging.getLogger(__name__)


async def fetch_all_options(currency: str) -> List[Dict]:
    """
    Fetch ALL active options for a currency from Deribit API.

    Args:
        currency: 'BTC' or 'ETH'

    Returns:
        List of instrument dictionaries with 'instrument_name', 'expiration_timestamp', etc.
    """
    url = "https://www.deribit.com/api/v2/public/get_instruments"
    params = {
        'currency': currency,
        'kind': 'option'
    }

    logger.info(f"Fetching ALL {currency} options from Deribit API...")

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"Deribit API error: {response.status}")

            data = await response.json()

            if 'result' not in data:
                raise Exception(f"Invalid Deribit API response: {data}")

            instruments = data['result']

            # Filter only active instruments
            active_instruments = [
                inst for inst in instruments
                if inst.get('is_active', True)
            ]

            logger.info(f"Retrieved {len(active_instruments)} active {currency} options from API")

            return active_instruments


async def filter_expired_instruments(instruments: List[Dict]) -> List[Dict]:
    """
    Filter out expired or about-to-expire instruments.

    Args:
        instruments: List of instrument dicts

    Returns:
        List of active (non-expired) instruments
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    buffer = timedelta(minutes=5)  # Filter instruments expiring within 5 minutes

    active = []
    for inst in instruments:
        expiry_ts = inst.get('expiration_timestamp')
        if expiry_ts:
            expiry_time = datetime.fromtimestamp(expiry_ts / 1000, tz=timezone.utc)
            if expiry_time > now + buffer:
                active.append(inst)

    logger.info(f"Filtered {len(instruments) - len(active)} expired instruments")
    return active


def partition_instruments(instruments: List[Dict], max_per_partition: int = 250) -> List[List[str]]:
    """
    Partition instruments into groups of max_per_partition.

    Args:
        instruments: List of instrument dicts
        max_per_partition: Maximum instruments per partition (default 250 = 500 channels)

    Returns:
        List of partitions, each containing list of instrument names
    """
    # Extract instrument names
    instrument_names = [inst['instrument_name'] for inst in instruments]

    # Partition using simple slicing (round-robin)
    partitions = []
    for i in range(0, len(instrument_names), max_per_partition):
        partition = instrument_names[i:i + max_per_partition]
        partitions.append(partition)

    logger.info(
        f"Partitioned {len(instrument_names)} instruments into "
        f"{len(partitions)} partitions (max {max_per_partition} per partition)"
    )

    for i, p in enumerate(partitions):
        logger.info(f"  Partition {i}: {len(p)} instruments")

    return partitions


async def get_partition_for_connection(
    currency: str,
    connection_id: int,
    max_per_partition: int = 250
) -> List[str]:
    """
    Get the instrument partition assigned to this connection.

    Args:
        currency: 'BTC' or 'ETH'
        connection_id: Connection ID (0-indexed)
        max_per_partition: Max instruments per partition

    Returns:
        List of instrument names assigned to this connection
    """
    # Fetch all options
    all_instruments = await fetch_all_options(currency)

    # Filter expired
    active_instruments = await filter_expired_instruments(all_instruments)

    # Partition
    partitions = partition_instruments(active_instruments, max_per_partition)

    # Validate connection_id
    if connection_id >= len(partitions):
        raise ValueError(
            f"CONNECTION_ID={connection_id} exceeds available partitions "
            f"(only {len(partitions)} partitions for {len(active_instruments)} instruments)"
        )

    # Return assigned partition
    assigned_partition = partitions[connection_id]

    logger.info(
        f"Connection {connection_id} assigned {len(assigned_partition)} instruments "
        f"(partition {connection_id+1}/{len(partitions)})"
    )

    return assigned_partition


async def main():
    """
    Main entry point for multi-connection orchestrator.
    This fetches the partition for this CONNECTION_ID and runs the WebSocket collector.
    """
    logger.info(f"Starting multi-connection orchestrator for {CURRENCY}, Connection ID: {CONNECTION_ID}")

    try:
        # Get assigned partition
        instruments = await get_partition_for_connection(CURRENCY, CONNECTION_ID)

        logger.info(f"Starting WebSocket collector for {len(instruments)} instruments...")
        logger.info(f"First 5 instruments: {instruments[:5]}")

        # Import and run the WebSocket collector
        from scripts.ws_tick_collector_multi import WebSocketTickCollector
        from scripts.collector_control_api import CollectorControlAPI

        WS_URL = os.getenv('DERIBIT_WS_URL', 'wss://www.deribit.com/ws/api/v2')
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/crypto_data')
        BUFFER_SIZE_QUOTES = int(os.getenv('BUFFER_SIZE_QUOTES', 200000))
        BUFFER_SIZE_TRADES = int(os.getenv('BUFFER_SIZE_TRADES', 100000))
        FLUSH_INTERVAL_SEC = int(os.getenv('FLUSH_INTERVAL_SEC', 3))

        # HTTP Control API port (base 8000 + CONNECTION_ID)
        CONTROL_API_PORT = int(os.getenv('CONTROL_API_PORT', 8000 + CONNECTION_ID))

        # Create collector with assigned instruments (override instrument fetching)
        collector = WebSocketTickCollector(
            ws_url=WS_URL,
            database_url=DATABASE_URL,
            currency=CURRENCY,
            top_n_instruments=0,  # Not used - we provide instruments directly
            buffer_size_quotes=BUFFER_SIZE_QUOTES,
            buffer_size_trades=BUFFER_SIZE_TRADES,
            flush_interval_sec=FLUSH_INTERVAL_SEC
        )

        # Override instruments list with our partition
        collector.instruments = instruments

        # Create and start HTTP control API
        control_api = CollectorControlAPI(
            collector=collector,
            host='0.0.0.0',
            port=CONTROL_API_PORT
        )

        logger.info(f"Starting HTTP control API on port {CONTROL_API_PORT}...")
        await control_api.start()

        # Start collector (skips instrument fetching since we already set instruments)
        logger.info(f"Starting collector for {CURRENCY} connection {CONNECTION_ID}...")

        # Run collector and API concurrently
        try:
            await collector.start()
        finally:
            await control_api.stop()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    # Run orchestrator
    asyncio.run(main())
