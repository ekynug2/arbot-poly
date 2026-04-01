"""
Structured logger for standard output + file logging using rich.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

from config.settings import Settings


def configure_logger(settings: Settings):
    """
    Sets up a global logger configuration:
    - Rich tracebacks and styles to stdout
    - Standard formatting to rotating file
    """
    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    
    # Ensure logs directory
    log_file_path = Path(settings.logging.file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # File Handler
    file_handler = RotatingFileHandler(
        str(log_file_path),
        maxBytes=settings.logging.max_log_size_mb * 1024 * 1024,
        backupCount=settings.logging.backup_count,
    )
    
    file_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Console Handler (Rich)
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_path=False
    )

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[console_handler, file_handler]
    )

    # Suppress verbose third-party loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.client").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
