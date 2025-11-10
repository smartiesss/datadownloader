"""
Instrument Fetcher - Multi-Currency Support
Supports BTC, ETH, and future currencies

This module fetches the top N options for any currency from Deribit REST API,
sorted by open interest (descending). Results are cached for 1 hour
to reduce API calls.

Usage:
    fetcher = MultiCurrencyInstrumentFetcher(currency='BTC')
    instruments = await fetcher.get_top_n_options(n=50)
    # Returns: ['BTC-29NOV24-100000-C', 'BTC-29NOV24-105000-C', ...]
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MultiCurrencyInstrumentFetcher:
    """
    Fetches top N options for any currency from Deribit by open interest.

    Features:
    - Support for multiple currencies (BTC, ETH, SOL, etc.)
    - REST API calls to Deribit
    - Sorts by open interest (descending)
    - 1-hour caching to reduce API load
    - Error handling with retries
    """

    def __init__(self, currency: str = "ETH", api_url: str = "https://www.deribit.com/api/v2"):
        """
        Initialize multi-currency instrument fetcher.

        Args:
            currency: Currency code (BTC, ETH, SOL, etc.)
            api_url: Deribit REST API base URL
        """
        self.currency = currency.upper()
        self.api_url = api_url
        self.cache: Optional[List[str]] = None
        self.cache_timestamp: Optional[datetime] = None
        self.cache_duration = timedelta(hours=1)

        logger.info(f"MultiCurrencyInstrumentFetcher initialized for {self.currency}")

    async def get_top_n_options(self, n: int = 50) -> List[str]:
        """
        Fetch top N options by open interest for configured currency.

        Args:
            n: Number of top instruments to return (default: 50)

        Returns:
            List of instrument names, e.g., ['BTC-29NOV24-100000-C', ...]

        Raises:
            Exception: If API call fails after retries
        """
        # Check cache first
        if self._is_cache_valid():
            logger.info(f"Using cached {self.currency} instruments ({len(self.cache)} instruments)")
            return self.cache[:n]

        logger.info(f"Fetching top {n} {self.currency} options from Deribit API...")

        try:
            instruments = await self._fetch_all_options()

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

            logger.info(f"Fetched {len(instrument_names)} {self.currency} options (top by open interest)")
            logger.debug(f"Top 5 instruments: {instrument_names[:5]}")

            return instrument_names

        except Exception as e:
            logger.error(f"Failed to fetch {self.currency} instruments: {e}")
            # Return cached data if available, even if stale
            if self.cache:
                logger.warning("Using stale cached data due to API error")
                return self.cache[:n]
            raise

    async def _fetch_all_options(self) -> List[Dict]:
        """
        Fetch all options for configured currency from Deribit API.

        Returns:
            List of instrument dictionaries with open interest data
        """
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    # Get all instruments for this currency
                    url = f"{self.api_url}/public/get_instruments"
                    params = {
                        'currency': self.currency,
                        'kind': 'option',
                        'expired': 'false'  # aiohttp requires string, not boolean
                    }

                    async with session.get(url, params=params, timeout=10) as response:
                        response.raise_for_status()
                        data = await response.json()

                        if 'result' not in data:
                            raise ValueError(f"Unexpected API response format: {data}")

                        instruments = data['result']
                        logger.info(f"Retrieved {len(instruments)} active {self.currency} options from API")
                        return instruments

            except aiohttp.ClientError as e:
                logger.warning(f"API request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise
            except Exception as e:
                logger.error(f"Unexpected error fetching {self.currency} instruments: {e}")
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
        logger.info(f"{self.currency} instrument cache cleared")


# Example usage and testing
async def main():
    """Test multi-currency instrument fetcher."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test with BTC
    btc_fetcher = MultiCurrencyInstrumentFetcher(currency='BTC')
    btc_instruments = await btc_fetcher.get_top_n_options(n=50)

    print(f"\nTop 50 BTC Options by Open Interest:")
    print("=" * 60)
    for i, instrument in enumerate(btc_instruments[:10], 1):  # Show first 10
        print(f"{i:2d}. {instrument}")

    # Test with ETH
    eth_fetcher = MultiCurrencyInstrumentFetcher(currency='ETH')
    eth_instruments = await eth_fetcher.get_top_n_options(n=50)

    print(f"\nTop 50 ETH Options by Open Interest:")
    print("=" * 60)
    for i, instrument in enumerate(eth_instruments[:10], 1):  # Show first 10
        print(f"{i:2d}. {instrument}")

    print(f"\nBTC: {len(btc_instruments)} instruments")
    print(f"ETH: {len(eth_instruments)} instruments")


if __name__ == "__main__":
    asyncio.run(main())
