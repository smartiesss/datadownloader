"""
Generate Test Logs for Rotation Verification
Task: T-004
Acceptance Criteria: AC-003

Generates specified size of log data to test file rotation.
Usage: python -m scripts.generate_test_logs --size 50
"""

import argparse
import logging
import sys
from pathlib import Path

# Import logging configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from logging_config import setup_logging


def generate_test_logs(size_mb=50):
    """
    Generate test logs to verify rotation

    Args:
        size_mb: Total size of logs to generate in MB
    """
    logger = setup_logging()

    # Calculate approximate number of log entries needed
    # Each log entry is roughly 150 bytes
    bytes_per_entry = 150
    target_bytes = size_mb * 1024 * 1024
    num_entries = target_bytes // bytes_per_entry

    logger.info(f"Generating {size_mb} MB of test logs ({num_entries:,} entries)...")

    for i in range(num_entries):
        logger.info(f"Test log entry {i+1:,}/{num_entries:,} - "
                   f"This is a test message to generate log data for rotation testing. "
                   f"The logging system should automatically rotate files at 10 MB.")

        if (i + 1) % 10000 == 0:
            logger.info(f"Progress: {((i+1)/num_entries)*100:.1f}% complete")

    logger.info(f"✓ Generated {size_mb} MB of test logs")
    logger.info(f"✓ Check logs/ directory for rotated files (app.log, app.log.1, app.log.2, etc.)")
    logger.info(f"✓ AC-003: Log file rotation test complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate test logs for rotation verification")
    parser.add_argument("--size", type=int, default=50, help="Size of logs to generate in MB (default: 50)")

    args = parser.parse_args()
    generate_test_logs(args.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
