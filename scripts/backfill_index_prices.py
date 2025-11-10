"""
Backfill historical index prices (BTC-USD, ETH-USD).

Index prices represent the spot price (weighted average of multiple exchanges).
Since Deribit doesn't provide historical index price API, we use perpetual
close prices as a proxy (perpetuals track index via arbitrage).

Usage:
    python -m scripts.backfill_index_prices
"""

import psycopg2
import logging
from datetime import datetime
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/index-prices-backfill.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class IndexPricesBackfiller:
    """Backfill historical index prices using perpetual close prices"""

    def __init__(self):
        self.conn = psycopg2.connect("dbname=crypto_data user=postgres")

    def backfill_from_perpetuals(self, currency: str):
        """
        Copy perpetual close prices as index prices.

        The perpetual futures price is designed to track the spot index price
        via arbitrage (funding rate mechanism). Therefore, perpetual close
        prices are a high-quality proxy for historical index prices.

        Args:
            currency: 'BTC' or 'ETH'
        """
        instrument = f"{currency}-PERPETUAL"

        logger.info(f"Backfilling {currency} index prices from {instrument}...")

        cur = self.conn.cursor()

        # Copy perpetual close prices to index_prices table
        query = """
        INSERT INTO index_prices (timestamp, currency, price)
        SELECT
            timestamp,
            %s AS currency,
            close AS price
        FROM perpetuals_ohlcv
        WHERE instrument = %s
        ON CONFLICT (timestamp, currency) DO UPDATE SET
            price = EXCLUDED.price
        """

        cur.execute(query, (currency, instrument))
        row_count = cur.rowcount
        self.conn.commit()

        logger.info(f"{currency}: Inserted {row_count:,} index prices")

        return row_count

    def verify_completeness(self, currency: str):
        """
        Verify index prices match perpetuals row count (should be 1:1).

        Args:
            currency: 'BTC' or 'ETH'
        """
        cur = self.conn.cursor()

        # Count index prices
        cur.execute("""
            SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM index_prices
            WHERE currency = %s
        """, (currency,))

        index_count, min_ts, max_ts = cur.fetchone()

        # Count perpetuals
        cur.execute("""
            SELECT COUNT(*)
            FROM perpetuals_ohlcv
            WHERE instrument = %s
        """, (f"{currency}-PERPETUAL",))

        perp_count = cur.fetchone()[0]

        # Check coverage
        coverage_pct = (index_count / perp_count * 100) if perp_count > 0 else 0

        logger.info(f"{currency} Index Prices:")
        logger.info(f"  Rows: {index_count:,}")
        logger.info(f"  Range: {min_ts} to {max_ts}")
        logger.info(f"  Coverage: {coverage_pct:.1f}% (vs. perpetuals)")

        if coverage_pct >= 99.9:
            logger.info(f"  ✅ Coverage OK")
        else:
            logger.warning(f"  ⚠️ Coverage below 100%")

        # Check for gaps
        cur.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT
                    timestamp,
                    LAG(timestamp) OVER (ORDER BY timestamp) AS prev_timestamp,
                    timestamp - LAG(timestamp) OVER (ORDER BY timestamp) AS gap
                FROM index_prices
                WHERE currency = %s
            ) gaps
            WHERE gap > INTERVAL '5 minutes'
        """, (currency,))

        gap_count = cur.fetchone()[0]

        if gap_count > 0:
            logger.warning(f"  ⚠️ {gap_count} gaps > 5 minutes detected")

            # Show largest gaps
            cur.execute("""
                SELECT
                    timestamp,
                    gap
                FROM (
                    SELECT
                        timestamp,
                        timestamp - LAG(timestamp) OVER (ORDER BY timestamp) AS gap
                    FROM index_prices
                    WHERE currency = %s
                ) gaps
                WHERE gap > INTERVAL '5 minutes'
                ORDER BY gap DESC
                LIMIT 10
            """, (currency,))

            for row in cur.fetchall():
                logger.warning(f"    Gap: {row[1]} at {row[0]}")
        else:
            logger.info(f"  ✅ No significant gaps detected")

    def verify_price_sanity(self, currency: str):
        """
        Verify index prices are reasonable (no outliers).

        Args:
            currency: 'BTC' or 'ETH'
        """
        cur = self.conn.cursor()

        # Check for zero/negative prices
        cur.execute("""
            SELECT COUNT(*)
            FROM index_prices
            WHERE currency = %s
              AND price <= 0
        """, (currency,))

        invalid_count = cur.fetchone()[0]

        if invalid_count > 0:
            logger.error(f"  ❌ {invalid_count} invalid prices (≤ 0)")
        else:
            logger.info(f"  ✅ No invalid prices")

        # Check for extreme outliers (>5 sigma from mean)
        cur.execute("""
            WITH stats AS (
                SELECT
                    AVG(price) AS mean_price,
                    STDDEV(price) AS stddev_price
                FROM index_prices
                WHERE currency = %s
            )
            SELECT COUNT(*)
            FROM index_prices i, stats s
            WHERE i.currency = %s
              AND ABS(i.price - s.mean_price) > 5 * s.stddev_price
        """, (currency, currency))

        outlier_count = cur.fetchone()[0]

        if outlier_count > 0:
            logger.warning(f"  ⚠️ {outlier_count} outliers (>5σ from mean)")
        else:
            logger.info(f"  ✅ No extreme outliers")

        # Show price statistics
        cur.execute("""
            SELECT
                MIN(price) AS min_price,
                MAX(price) AS max_price,
                AVG(price) AS avg_price,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) AS median_price
            FROM index_prices
            WHERE currency = %s
        """, (currency,))

        stats = cur.fetchone()
        logger.info(f"  Price Stats:")
        logger.info(f"    Min: ${stats[0]:,.2f}")
        logger.info(f"    Max: ${stats[1]:,.2f}")
        logger.info(f"    Avg: ${stats[2]:,.2f}")
        logger.info(f"    Median: ${stats[3]:,.2f}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main execution function"""
    currencies = ['BTC', 'ETH']

    logger.info("=" * 60)
    logger.info("Index Prices Backfill Started")
    logger.info("=" * 60)
    logger.info(f"Currencies: {currencies}")
    logger.info(f"Method: Copy from perpetuals close prices")
    logger.info("")

    backfiller = IndexPricesBackfiller()

    try:
        total_rows = 0

        for currency in currencies:
            count = backfiller.backfill_from_perpetuals(currency)
            total_rows += count
            logger.info("")

            # Verify completeness
            backfiller.verify_completeness(currency)
            logger.info("")

            # Verify price sanity
            backfiller.verify_price_sanity(currency)
            logger.info("")

        logger.info("=" * 60)
        logger.info(f"Backfill Complete! Total rows: {total_rows:,}")
        logger.info("=" * 60)

        # Show final table size
        cur = backfiller.conn.cursor()
        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('index_prices'))")
        table_size = cur.fetchone()[0]
        logger.info(f"Index prices table size: {table_size}")

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise

    finally:
        backfiller.close()


if __name__ == '__main__':
    main()
