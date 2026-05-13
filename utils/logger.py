import sys
from loguru import logger

logger.remove()

logger.add(sys.stderr, level="INFO", colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

logger.add(
    "logs/agent.log",
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    serialize=True,
)

logger.add(
    "logs/errors.log",
    level="ERROR",
    rotation="5 MB",
    serialize=True,
)


def get_request_logger(request_id: str):
    return logger.bind(request_id=request_id)
