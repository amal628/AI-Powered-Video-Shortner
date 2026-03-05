"""
Comprehensive logging configuration for the AI Video Shortener application.

✔ Fully Pylance-clean
✔ Type-safe
✔ Rotating file handlers
✔ Module-specific loggers
✔ No duplicate handler stacking
✔ Production-ready
"""

import logging
import logging.config
from logging.handlers import RotatingFileHandler
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# ------------------------------------------------------------------ #
# Log Directory Setup
# ------------------------------------------------------------------ #

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

APP_LOG_FILE = LOGS_DIR / "app.log"
ERROR_LOG_FILE = LOGS_DIR / "error.log"
PROCESSING_LOG_FILE = LOGS_DIR / "processing.log"
API_LOG_FILE = LOGS_DIR / "api.log"
SECURITY_LOG_FILE = LOGS_DIR / "security.log"
PERFORMANCE_LOG_FILE = LOGS_DIR / "performance.log"


# ------------------------------------------------------------------ #
# Main Logging Setup
# ------------------------------------------------------------------ #

def setup_logging(level: str = "INFO", log_format: Optional[str] = None) -> None:
    """
    Configure application-wide logging.
    """

    if log_format is None:
        log_format = (
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        )

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": log_format,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {
                "format": "%(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "standard",
                "stream": sys.stdout,
            },
            "file_app": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(APP_LOG_FILE),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "file_error": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "standard",
                "filename": str(ERROR_LOG_FILE),
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "root": {
            "handlers": ["console", "file_app"],
            "level": level,
        },
    }

    logging.config.dictConfig(config)

    # Add extended module loggers safely
    _setup_extended_loggers()


# ------------------------------------------------------------------ #
# Extended Module Loggers
# ------------------------------------------------------------------ #

def _setup_extended_loggers() -> None:
    """
    Configure additional rotating file loggers.
    Prevents duplicate handlers.
    """

    _configure_rotating_logger(
        logger_name="app.processing",
        file_path=PROCESSING_LOG_FILE,
        level=logging.DEBUG,
    )

    _configure_rotating_logger(
        logger_name="app.api",
        file_path=API_LOG_FILE,
        level=logging.INFO,
    )

    _configure_rotating_logger(
        logger_name="app.security",
        file_path=SECURITY_LOG_FILE,
        level=logging.WARNING,
    )

    _configure_rotating_logger(
        logger_name="app.performance",
        file_path=PERFORMANCE_LOG_FILE,
        level=logging.INFO,
    )


def _configure_rotating_logger(
    logger_name: str,
    file_path: Path,
    level: int,
) -> None:
    """
    Safely attach a rotating file handler to a logger
    without duplicating handlers on reload.
    """

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    # Avoid duplicate handlers
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            return

    handler = RotatingFileHandler(
        file_path,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=3,
        encoding="utf8",
    )

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        )
    )

    logger.addHandler(handler)


# ------------------------------------------------------------------ #
# Utility Functions
# ------------------------------------------------------------------ #

def get_logger(name: str) -> logging.Logger:
    """Return configured logger."""
    return logging.getLogger(name)


def log_exception(
    logger: logging.Logger,
    exc: Exception,
    context: Optional[str] = None,
) -> None:
    """Log exception with traceback."""

    message = "Exception occurred"
    if context:
        message += f" in {context}"
    message += f": {exc}"

    logger.error(message, exc_info=True)


def log_performance(
    operation: str,
    duration: float,
    **extra: Any,
) -> None:
    """Log performance metrics."""

    perf_logger = logging.getLogger("app.performance")

    metrics: Dict[str, Any] = {
        "operation": operation,
        "duration_seconds": round(duration, 4),
        **extra,
    }

    perf_logger.info(f"Performance: {metrics}")


def log_security_event(
    event_type: str,
    details: Dict[str, Any],
) -> None:
    """Log security events."""

    security_logger = logging.getLogger("app.security")
    security_logger.warning(f"Security Event [{event_type}]: {details}")


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration: float,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Log API request metadata."""

    api_logger = logging.getLogger("app.api")

    request_data: Dict[str, Any] = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_seconds": round(duration, 4),
        "timestamp": datetime.utcnow().isoformat(),
    }

    if user_agent:
        request_data["user_agent"] = user_agent[:200]

    if ip_address:
        request_data["ip_address"] = ip_address

    api_logger.info(f"API Request: {request_data}")


# ------------------------------------------------------------------ #
# Initialize Automatically
# ------------------------------------------------------------------ #

setup_logging()