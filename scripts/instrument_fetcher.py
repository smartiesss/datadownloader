"""
Instrument Fetcher - Fetch Top 50 ETH Options by Open Interest
Task: T-001
Acceptance Criteria: AC-001 (Data completeness)

This module fetches the top 50 ETH options from Deribit REST API,
sorted by open interest (descending). Results are cached for 1 hour
to reduce API calls during POC.

Usage:
    fetcher = InstrumentFetcher()
    instruments = await fetcher.get_top_n_eth_options(n=50)
    # Returns: ['ETH-29NOV24-2000-C', 'ETH-29NOV24-2100-C', ...]
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InstrumentFetcher:
    """
    Fetches top N ETH options from Deribit by open interest.

    Features:
    - REST API calls to Deribit
    - Sorts by open interest (descending)
    - 1-hour caching to reduce API load
    - Error handling with retries
    """

    def __init__(self, api_url: str = "https://www.deribit.com/api/v2"):
        """
        Initialize instrument fetcher.

        Args:
            api_url: Deribit REST API base URL
        """
        self.api_url = api_url
        self.cache: Optional[List[str]] = None
        self.cache_timestamp: Optional[datetime] = None
        self.cache_duration = timedelta(hours=1)

    async def get_top_n_eth_options(self, n: int = 50) -> List[str]:
        """
        Fetch top N ETH options by open interest.

        Args:
            n: Number of top instruments to return (default: 50)

        Returns:
            List of instrument names, e.g., ['ETH-29NOV24-2000-C', ...]

        Raises:
            Exception: If API call fails after retries
        """
        # Check cache first
        if self._is_cache_valid():
            logger.info(f"Using cached instruments ({len(self.cache)} instruments)")
            return self.cache[:n]

        logger.info(f"Fetching top {n} ETH options from Deribit API...")

        try:
            instruments = await self._fetch_all_eth_options()

            # Filter out expired and invalid options
            active_instruments = [
                inst for inst in instruments
                if inst.get('settlement_period') != 'expired'
                and inst.get('kind') == 'option'
                and inst.get('is_active', False)
            ]

            # Sort by open interest (descending)
            sorted_instruments = sorted(
                active_instruments,
                key=lambda x: float(x.get('open_interest', 0)),
                reverse=True
            )

            # Extract instrument names
            instrument_names = [inst['instrument_name'] for inst in sorted_instruments[:n]]

            # Update cache
            self.cache = instrument_names
            self.cache_timestamp = datetime.now()

            logger.info(f"Fetched {len(instrument_names)} ETH options (top by open interest)")
            logger.debug(f"Top 5 instruments: {instrument_names[:5]}")

            return instrument_names

        except Exception as e:
            logger.error(f"Failed to fetch instruments: {e}")
            # Return cached data if available, even if stale
            if self.cache:
                logger.warning("Using stale cached data due to API error")
                return self.cache[:n]
            raise

    async def _fetch_all_eth_options(self) -> List[Dict]:
        """
        Fetch all ETH options from Deribit API.

        Returns:
            List of instrument dictionaries with open interest data
        """
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    # Get all ETH instruments
                    url = f"{self.api_url}/public/get_instruments"
                    params = {
                        'currency': 'ETH',
                        'kind': 'option',
                        'expired': 'false'  # aiohttp requires string, not boolean
                    }

                    async with session.get(url, params=params, timeout=10) as response:
                        response.raise_for_status()
                        data = await response.json()

                        if 'result' not in data:
                            raise ValueError(f"Unexpected API response format: {data}")

                        instruments = data['result']
                        logger.info(f"Retrieved {len(instruments)} active ETH options from API")
                        return instruments

            except aiohttp.ClientError as e:
                logger.warning(f"API request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise
            except Exception as e:
                logger.error(f"Unexpected error fetching instruments: {e}")
                raise

    def _is_cache_valid(self) -> bool:
        """
        Check if cached data is still valid.

        Returns:
            True if cache exists and is less than 1 hour old
        """
        if self.cache is None or self.cache_timestamp is None:
            return False

        age = datetime.now() - self.cache_timestamp
        is_valid = age < self.cache_duration

        if not is_valid:
            logger.debug(f"Cache expired (age: {age.total_seconds():.0f}s)")

        return is_valid

    def clear_cache(self):
        """Clear cached instrument data (useful for testing)."""
        self.cache = None
        self.cache_timestamp = None
        logger.info("Instrument cache cleared")


# Example usage and testing
async def main():
    """Test instrument fetcher."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    fetcher = InstrumentFetcher()

    # Fetch top 50 ETH options
    instruments = await fetcher.get_top_n_eth_options(n=50)

    print(f"\nTop 50 ETH Options by Open Interest:")
    print("=" * 60)
    for i, instrument in enumerate(instruments, 1):
        print(f"{i:2d}. {instrument}")

    # Test cache
    print(f"\nTesting cache (should be instant)...")
    instruments_cached = await fetcher.get_top_n_eth_options(n=50)
    assert instruments == instruments_cached, "Cache mismatch!"
    print("Cache working correctly!")


if __name__ == "__main__":
    asyncio.run(main())
