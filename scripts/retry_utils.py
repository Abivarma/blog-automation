"""
Retry utilities with exponential backoff.
"""

import time
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def retry(max_attempts: int = 3, backoff_factor: float = 2.0, exceptions: tuple = (Exception,)):
    """Decorator for retrying functions with exponential backoff."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait = backoff_factor ** attempt
                        logger.warning(
                            f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {wait:.1f}s..."
                        )
                        time.sleep(wait)
                    else:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
            raise last_exception

        return wrapper

    return decorator
