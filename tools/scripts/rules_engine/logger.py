import sys

from loguru import logger

__all__ = ["logger"]

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
)
