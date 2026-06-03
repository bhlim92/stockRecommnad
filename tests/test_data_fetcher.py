import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from app.data_fetcher import AssetDataFetcher

def test_period_to_start_date():
    fetcher = AssetDataFetcher()
    # Test different period strings conversion
    date_1mo = fetcher._period_to_start_date("1mo")
    date_1y = fetcher._period_to_start_date("1y")
    date_invalid = fetcher._period_to_start_date("invalid")
    
    assert len(date_1mo) == 10  # YYYY-MM-DD
    assert len(date_1y) == 10
    assert len(date_invalid) == 10
    assert date_1mo > date_1y  # 1mo ago is more recent than 1y ago

@patch("app.data_fetcher.yf.Ticker")
def test_fetch_historical_prices_us(mock_ticker, sample_stock_df):
    mock_instance = MagicMock()
    mock_instance.history.return_value = sample_stock_df
    mock_ticker.return_value = mock_instance
    
    fetcher = AssetDataFetcher()
    df = fetcher.fetch_historical_prices("AAPL", period="1y")
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    mock_ticker.assert_called_once_with("AAPL")
    mock_instance.history.assert_called_once()

@patch("app.data_fetcher.fdr.DataReader")
def test_fetch_historical_prices_kr(mock_fdr_reader, sample_stock_df):
    # Standard FDR columns (might be lowercase or uppercase)
    fdr_df = sample_stock_df.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"
    })
    mock_fdr_reader.return_value = fdr_df
    
    fetcher = AssetDataFetcher()
    df = fetcher.fetch_historical_prices("005930.KS", period="1y")
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    mock_fdr_reader.assert_called_once()

@patch("app.data_fetcher.fdr.DataReader")
@patch("app.data_fetcher.yf.Ticker")
def test_fetch_historical_prices_kr_fallback(mock_ticker, mock_fdr_reader, sample_stock_df):
    # FDR throws exception, fallback to yfinance
    mock_fdr_reader.side_effect = Exception("FDR Error")
    mock_instance = MagicMock()
    mock_instance.history.return_value = sample_stock_df
    mock_ticker.return_value = mock_instance
    
    fetcher = AssetDataFetcher()
    df = fetcher.fetch_historical_prices("005930.KS", period="1y")
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    mock_fdr_reader.assert_called_once()
    mock_ticker.assert_called_once_with("005930.KS")

@patch("app.data_fetcher.yf.Ticker")
def test_fetch_historical_prices_empty_fail(mock_ticker):
    mock_instance = MagicMock()
    mock_instance.history.return_value = pd.DataFrame()
    mock_ticker.return_value = mock_instance
    
    fetcher = AssetDataFetcher()
    with pytest.raises(ConnectionError):
        # The retry decorator will retry 3 times, then raise the final Exception
        fetcher.fetch_historical_prices("INVALID_TICKER", period="1y")

@patch("app.data_fetcher.yf.Ticker")
def test_fetch_bond_yield(mock_ticker):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=5, freq="D")
    yield_df = pd.DataFrame({"Close": [4.1, 4.2, 4.3, 4.2, 4.15]}, index=dates)
    
    mock_instance = MagicMock()
    mock_instance.history.return_value = yield_df
    mock_ticker.return_value = mock_instance
    
    fetcher = AssetDataFetcher()
    df = fetcher.fetch_bond_yield("^TNX", period="1y")
    
    assert isinstance(df, pd.DataFrame)
    assert "Yield" in df.columns
    assert df["Yield"].iloc[-1] == 4.15

@patch("app.data_fetcher.fdr.DataReader")
def test_fetch_fred_indicator(mock_fdr_reader):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=5, freq="MS")
    fred_df = pd.DataFrame({"CPIAUCSL": [300.1, 300.5, 301.2, 301.5, 302.0]}, index=dates)
    mock_fdr_reader.return_value = fred_df
    
    fetcher = AssetDataFetcher()
    df = fetcher.fetch_fred_indicator("CPIAUCSL", start_date="2023-01-01")
    
    assert isinstance(df, pd.DataFrame)
    assert "Value" in df.columns
    assert df["Value"].iloc[-1] == 302.0
