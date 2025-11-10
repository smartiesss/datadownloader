"""
Data Quality Checks for Perpetuals OHLCV
Task: T-008
Acceptance Criteria: AC-004, AC-005

Runs data quality validation on perpetuals_ohlcv table:
1. Gap Detection (gaps >5 minutes)
2. OHLCV Sanity Checks (high >= low, close in [low, high])
3. Row Count and Coverage

Usage:
    python -m scripts.data_quality_checks --table perpetuals_ohlcv
"""

import argparse
import psycopg2
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from logging_config import setup_logging


class DataQualityChecker:
    """Performs data quality checks on OHLCV tables"""

    def __init__(self, db_connection_string="dbname=crypto_data user=postgres"):
        self.db_conn_str = db_connection_string
        self.logger = setup_logging()
        self.evidence_dir = Path(__file__).parent.parent / "tests" / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """Create database connection"""
        return psycopg2.connect(self.db_conn_str)

    def check_gaps(self, table_name, gap_threshold_minutes=5):
        """
        Check for gaps >5 minutes in time series data

        Args:
            table_name: Table to check
            gap_threshold_minutes: Gap threshold in minutes (default: 5)

        Returns:
            list: List of gaps found
        """
        self.logger.info(f"Running gap detection on {table_name}...")

        conn = self.connect()
        try:
            cursor = conn.cursor()

            # Gap detection query
            query = f"""
                WITH gaps AS (
                    SELECT
                        instrument,
                        timestamp,
                        LAG(timestamp) OVER (PARTITION BY instrument ORDER BY timestamp) AS prev_timestamp,
                        timestamp - LAG(timestamp) OVER (PARTITION BY instrument ORDER BY timestamp) AS gap
                    FROM {table_name}
                )
                SELECT
                    instrument,
                    prev_timestamp AS gap_start,
                    timestamp AS gap_end,
                    EXTRACT(EPOCH FROM gap) / 60 AS gap_minutes
                FROM gaps
                WHERE gap > INTERVAL '{gap_threshold_minutes} minutes'
                ORDER BY gap DESC
                LIMIT 100;
            """

            cursor.execute(query)
            gaps = cursor.fetchall()

            # Save to CSV
            output_file = self.evidence_dir / "T-008-gap-report.csv"
            with open(output_file, 'w') as f:
                f.write("instrument,gap_start,gap_end,gap_minutes\n")
                for row in gaps:
                    f.write(f"{row[0]},{row[1]},{row[2]},{row[3]:.2f}\n")

            self.logger.info(
                f"Gap detection complete: {len(gaps)} gaps >{gap_threshold_minutes} minutes found"
            )
            self.logger.info(f"Evidence saved to {output_file}")

            if gaps:
                self.logger.warning(f"Top 5 largest gaps:")
                for i, gap in enumerate(gaps[:5], 1):
                    self.logger.warning(
                        f"  {i}. {gap[0]}: {gap[3]:.1f} minutes "
                        f"({gap[1]} → {gap[2]})"
                    )

            return gaps

        finally:
            conn.close()

    def check_ohlcv_sanity(self, table_name):
        """
        Check OHLCV sanity (high >= low, close in [low, high], prices > 0)

        Args:
            table_name: Table to check

        Returns:
            int: Number of violations found
        """
        self.logger.info(f"Running OHLCV sanity checks on {table_name}...")

        conn = self.connect()
        try:
            cursor = conn.cursor()

            # Sanity check query
            query = f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE high < low
                   OR close < low
                   OR close > high
                   OR open <= 0
                   OR high <= 0
                   OR low <= 0
                   OR close <= 0
                   OR volume < 0;
            """

            cursor.execute(query)
            violation_count = cursor.fetchone()[0]

            # Save detailed violations if any found
            if violation_count > 0:
                detail_query = f"""
                    SELECT instrument, timestamp, open, high, low, close, volume
                    FROM {table_name}
                    WHERE high < low
                       OR close < low
                       OR close > high
                       OR open <= 0
                       OR high <= 0
                       OR low <= 0
                       OR close <= 0
                       OR volume < 0
                    ORDER BY timestamp DESC
                    LIMIT 100;
                """
                cursor.execute(detail_query)
                violations = cursor.fetchall()

                output_file = self.evidence_dir / "T-008-sanity-report.csv"
                with open(output_file, 'w') as f:
                    f.write("instrument,timestamp,open,high,low,close,volume\n")
                    for row in violations:
                        f.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]}\n")

                self.logger.error(
                    f"OHLCV sanity check FAILED: {violation_count} violations found"
                )
                self.logger.error(f"Details saved to {output_file}")
            else:
                # Create empty report file
                output_file = self.evidence_dir / "T-008-sanity-report.csv"
                with open(output_file, 'w') as f:
                    f.write("instrument,timestamp,open,high,low,close,volume\n")
                    f.write("# No violations found\n")

                self.logger.info("✓ OHLCV sanity check PASSED: 0 violations")
                self.logger.info(f"Evidence saved to {output_file}")

            return violation_count

        finally:
            conn.close()

    def check_row_counts(self, table_name):
        """
        Check row counts and coverage by instrument

        Args:
            table_name: Table to check

        Returns:
            list: Row count details by instrument
        """
        self.logger.info(f"Running row count checks on {table_name}...")

        conn = self.connect()
        try:
            cursor = conn.cursor()

            # Row count query
            query = f"""
                SELECT
                    instrument,
                    COUNT(*) AS row_count,
                    MIN(timestamp) AS first_candle,
                    MAX(timestamp) AS last_candle,
                    EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / 60 AS duration_minutes
                FROM {table_name}
                GROUP BY instrument
                ORDER BY instrument;
            """

            cursor.execute(query)
            results = cursor.fetchall()

            # Save to file
            output_file = self.evidence_dir / "T-008-row-counts.txt"
            with open(output_file, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write(f"Row Count Report - {table_name}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")

                for row in results:
                    instrument, count, first, last, duration = row
                    expected_candles = int(duration)  # 1-minute candles
                    coverage = (count / expected_candles * 100) if expected_candles > 0 else 0

                    f.write(f"Instrument: {instrument}\n")
                    f.write(f"  Row Count:      {count:,}\n")
                    f.write(f"  First Candle:   {first}\n")
                    f.write(f"  Last Candle:    {last}\n")
                    f.write(f"  Duration:       {duration/60/24:.1f} days ({duration:,.0f} minutes)\n")
                    f.write(f"  Expected:       {expected_candles:,} candles\n")
                    f.write(f"  Coverage:       {coverage:.2f}%\n")
                    f.write("\n")

                    self.logger.info(
                        f"{instrument}: {count:,} candles "
                        f"({first} → {last}, {coverage:.2f}% coverage)"
                    )

            self.logger.info(f"Row count report saved to {output_file}")

            return results

        finally:
            conn.close()

    def run_all_checks(self, table_name):
        """
        Run all data quality checks

        Args:
            table_name: Table to check

        Returns:
            dict: Results summary
        """
        self.logger.info(f"Starting data quality checks for {table_name}...")
        self.logger.info("=" * 80)

        results = {
            "table": table_name,
            "timestamp": datetime.now().isoformat(),
            "gaps": [],
            "violations": 0,
            "row_counts": []
        }

        try:
            # Check 1: Gap Detection
            results["gaps"] = self.check_gaps(table_name)
            self.logger.info("")

            # Check 2: OHLCV Sanity
            results["violations"] = self.check_ohlcv_sanity(table_name)
            self.logger.info("")

            # Check 3: Row Counts
            results["row_counts"] = self.check_row_counts(table_name)
            self.logger.info("")

            # Summary
            self.logger.info("=" * 80)
            self.logger.info("DATA QUALITY CHECK SUMMARY")
            self.logger.info("=" * 80)
            self.logger.info(f"Table: {table_name}")
            self.logger.info(f"Gaps (>5 min): {len(results['gaps'])}")
            self.logger.info(f"OHLCV Violations: {results['violations']}")
            self.logger.info(f"Instruments: {len(results['row_counts'])}")

            if len(results['gaps']) == 0 and results['violations'] == 0:
                self.logger.info("✓ All data quality checks PASSED")
            else:
                self.logger.warning("⚠ Some data quality issues found - see evidence files")

            self.logger.info("=" * 80)

            return results

        except Exception as e:
            self.logger.error(f"Data quality check failed: {e}")
            raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run data quality checks on OHLCV tables"
    )
    parser.add_argument(
        "--table",
        type=str,
        default="perpetuals_ohlcv",
        help="Table name to check (default: perpetuals_ohlcv)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="dbname=crypto_data user=postgres",
        help="PostgreSQL connection string"
    )

    args = parser.parse_args()

    # Create checker and run
    checker = DataQualityChecker(args.db)

    try:
        checker.run_all_checks(args.table)
        return 0
    except Exception as e:
        checker.logger.error(f"Data quality checks failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
