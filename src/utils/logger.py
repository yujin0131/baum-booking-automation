"""
Logging configuration using loguru
Loguru를 사용한 로깅 설정
"""
import sys
from pathlib import Path
from loguru import logger

from config.settings import settings


def setup_logging():
    """
    Setup application logging with loguru

    Features:
    - Console output with colored formatting
    - File rotation (10 MB per file)
    - Log retention (30 days)
    - Separate error log file
    - Separate SMS log file
    """

    # Remove default handler
    logger.remove()

    # Determine log level
    log_level = settings.log_level.upper()

    # Console handler - with colors
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Main application log file
    logger.add(
        log_dir / "app.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )

    # Error log file - only errors and above
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # SMS-specific log file
    logger.add(
        log_dir / "sms.log",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        rotation="10 MB",
        retention="60 days",
        compression="zip",
        encoding="utf-8",
        filter=lambda record: "SMS" in record["message"] or record.get("extra", {}).get("type") == "sms",
    )

    logger.info(f"Logging initialized - Level: {log_level}")
    logger.info(f"Log directory: {log_dir.absolute()}")
