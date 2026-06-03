import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from typing import Optional
from app.utils.helpers import retry_api_call, clean_ticker_for_fdr
from app.utils.logger import setup_logger

logger = setup_logger("data_fetcher", "logs/app.log")

class AssetDataFetcher:
    """
    Handles API integration with yfinance and FinanceDataReader to fetch stock history,
    treasury yields, commodities, exchange rates, and FRED macro indicators.
    """
    
    def __init__(self, request_timeout: int = 15) -> None:
        """
        Initializes fetcher client parameters.
        
        Args:
            request_timeout: Connection timeout duration in seconds.
        """
        self.timeout = request_timeout

    def _period_to_start_date(self, period: str) -> str:
        """Converts yfinance period string into a start date string (YYYY-MM-DD)."""
        today = datetime.today()
        if period == "1mo":
            dt = today - timedelta(days=30)
        elif period == "3mo":
            dt = today - timedelta(days=90)
        elif period == "6mo":
            dt = today - timedelta(days=180)
        elif period == "1y":
            dt = today - timedelta(days=365)
        elif period == "2y":
            dt = today - timedelta(days=365 * 2)
        elif period == "5y":
            dt = today - timedelta(days=365 * 5)
        else:
            dt = today - timedelta(days=365)
        return dt.strftime("%Y-%m-%d")

    @retry_api_call(max_retries=3, initial_delay=2.0, backoff_factor=2.0)
    def fetch_historical_prices(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """
        Fetches historical price data for a single asset.
        
        Args:
            ticker: Asset identifier (e.g. "AAPL", "005930.KS", "GLD").
            period: Time window (e.g., "1y", "6mo", "1mo").
            interval: Time frequency (e.g., "1d", "1wk").
            
        Returns:
            Pandas DataFrame containing 'Open', 'High', 'Low', 'Close', 'Volume'.
            
        Raises:
            ConnectionError: If network fetch fails.
            ValueError: If ticker name is incorrect or no rows return.
        """
        logger.info(f"Fetching historical prices for {ticker} (period: {period}, interval: {interval})")
        
        # Identify if ticker is Korean (ends with .KS/.KQ, or is 6 digits)
        is_korean = ticker.endswith(".KS") or ticker.endswith(".KQ") or (ticker.isdigit() and len(ticker) == 6)
        
        if is_korean:
            fdr_code = clean_ticker_for_fdr(ticker)
            start_date = self._period_to_start_date(period)
            try:
                df = fdr.DataReader(fdr_code, start=start_date)
                if df is not None and not df.empty:
                    # FDR columns standard is: Open, High, Low, Close, Volume, Change
                    df = df.rename(columns={
                        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
                        "Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"
                    })
                    # Ensure required columns are present
                    cols_needed = ["Open", "High", "Low", "Close", "Volume"]
                    for col in cols_needed:
                        if col not in df.columns:
                            df[col] = 0.0
                    return df[cols_needed]
            except Exception as e:
                logger.warning(f"FinanceDataReader failed for {ticker}: {str(e)}. Falling back to yfinance.")
        
        # Use yfinance as standard/fallback
        try:
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(period=period, interval=interval, timeout=self.timeout)
            if df.empty:
                raise ValueError(f"No historical price data returned for ticker: {ticker}")
            cols_needed = ["Open", "High", "Low", "Close", "Volume"]
            return df[cols_needed]
        except Exception as e:
            logger.error(f"Failed to fetch {ticker} via yfinance: {str(e)}")
            raise ConnectionError(f"Error fetching historical prices for {ticker}: {str(e)}")

    @retry_api_call(max_retries=3, initial_delay=2.0, backoff_factor=2.0)
    def fetch_bond_yield(self, yield_ticker: str, period: str = "1y") -> pd.DataFrame:
        """
        Fetches historical US or Korean treasury yields.
        
        Args:
            yield_ticker: Yield ticker symbol (e.g. "^TNX" for US 10Y).
            period: History duration.
            
        Returns:
            DataFrame containing bond yield percentage values.
        """
        logger.info(f"Fetching bond yield for {yield_ticker} (period: {period})")
        try:
            ticker_obj = yf.Ticker(yield_ticker)
            df = ticker_obj.history(period=period, timeout=self.timeout)
            if df.empty:
                raise ValueError(f"No yield data returned for ticker: {yield_ticker}")
            
            # The closing yield value in yfinance is the interest rate percentage
            df = df.rename(columns={"Close": "Yield", "close": "Yield"})
            if "Yield" not in df.columns:
                if "Close" in df.columns:
                    df["Yield"] = df["Close"]
                else:
                    df["Yield"] = df.iloc[:, 0]
            return df[["Yield"]]
        except Exception as e:
            logger.error(f"Failed to fetch yield for {yield_ticker}: {str(e)}")
            raise ConnectionError(f"Error fetching yield for {yield_ticker}: {str(e)}")

    @retry_api_call(max_retries=3, initial_delay=2.0, backoff_factor=2.0)
    def fetch_fred_indicator(self, indicator_id: str, start_date: str) -> pd.DataFrame:
        """
        Retrieves economic indicator records from FRED using FinanceDataReader.
        
        Args:
            indicator_id: FRED economic indicator identifier (e.g. "CPIAUCSL").
            start_date: Start date for query (format YYYY-MM-DD).
            
        Returns:
            DataFrame containing historical economic observations.
        """
        logger.info(f"Fetching FRED indicator {indicator_id} starting from {start_date}")
        try:
            symbol = f"FRED:{indicator_id}"
            df = fdr.DataReader(symbol, start=start_date)
            if df.empty:
                raise ValueError(f"No FRED data returned for: {indicator_id}")
            
            # Standardize the target value column name
            if indicator_id in df.columns:
                df = df.rename(columns={indicator_id: "Value"})
            else:
                df.columns = ["Value"] + list(df.columns[1:])
            return df[["Value"]]
        except Exception as e:
            logger.error(f"Failed to fetch FRED indicator {indicator_id}: {str(e)}")
            raise ConnectionError(f"Error fetching FRED indicator {indicator_id}: {str(e)}")
