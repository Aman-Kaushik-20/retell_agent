import sys

from loguru import logger as _logger
# Simple Logging Util
_logger.remove()
_logger.add(
    sys.stdout,
    level="INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level:<8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

logger = _logger
