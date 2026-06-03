import time
import functools
from typing import Callable, Any
from app.utils.logger import setup_logger

def retry_api_call(max_retries: int = 3, initial_delay: float = 2.0, backoff_factor: float = 2.0) -> Callable:
    """
    Decorator implementing exponential backoff for network API connections.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial wait time in seconds.
        backoff_factor: Multiplier applied to delay after each failure.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = setup_logger("retry_helper", "logs/app.log")
            delay = initial_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(
                        f"Attempt {attempt} failed in function '{func.__name__}': {str(e)}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    if attempt == max_retries:
                        logger.error(f"Function '{func.__name__}' failed after {max_retries} attempts.")
                        raise e
                    time.sleep(delay)
                    delay *= backoff_factor
            return None
        return wrapper
    return decorator

def get_date_n_days_ago(days: int) -> str:
    """
    Returns the ISO date string for N days ago.
    Format: YYYY-MM-DD
    """
    from datetime import datetime, timedelta
    target_date = datetime.now() - timedelta(days=days)
    return target_date.strftime("%Y-%m-%d")

def clean_ticker_for_fdr(ticker: str) -> str:
    """
    Converts yfinance ticker to FinanceDataReader code.
    E.g. "005930.KS" -> "005930", "AAPL" -> "AAPL"
    """
    if "." in ticker:
        parts = ticker.split(".")
        if parts[0].isdigit():
            return parts[0]
    return ticker
