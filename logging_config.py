"""
Logging Configuration with File Rotation
Task: T-004
Acceptance Criteria: AC-003

Configures Python logging with rotating file handlers.
- Max 10 MB per file
- Keep 5 backup files
- Auto-creates logs/ directory
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir="logs", log_level=logging.INFO):
    """
    Configure logging with file rotation

    Args:
        log_dir: Directory for log files (default: "logs")
        log_level: Logging level (default: INFO)

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Configure rotating file handler
    log_file = log_path / "app.log"
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )

    # Set format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.addHandler(handler)

    # Also add console handler for immediate feedback
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"✓ Logging configured: {log_file}")
    logger.info(f"  Max file size: 10 MB")
    logger.info(f"  Backup count: 5")

    return logger


if __name__ == "__main__":
    # Test logging configuration
    logger = setup_logging()
    logger.info("Test log entry - logging configuration successful")
    logger.info(f"✓ AC-003: Log file rotation configured")
