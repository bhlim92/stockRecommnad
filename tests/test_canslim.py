import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from app.canslim import CanslimScreener

@pytest.fixture
def mock_fetcher(sample_stock_df):
    fetcher = MagicMock()
    # Return standard stock df for RS and SMA checks
    fetcher.fetch_historical_prices.return_value = sample_stock_df
    return fetcher

def test_extract_eps_or_net_income():
    screener = CanslimScreener(data_fetcher=None)
    df = pd.DataFrame([[1.0, 2.0]], index=["Basic EPS"], columns=["2025-12-31", "2024-12-31"])
    series = screener._extract_eps_or_net_income(df)
    assert series is not None
    assert series.iloc[0] == 1.0

@patch("app.canslim.yf.Ticker")
def test_evaluate_growth_rate(mock_ticker, sample_quarterly_financials_df):
    mock_instance = MagicMock()
    mock_instance.quarterly_financials = sample_quarterly_financials_df
    mock_ticker.return_value = mock_instance
    
    screener = CanslimScreener(data_fetcher=None)
    yoy, qoq = screener.evaluate_growth_rate("AAPL")
    
    # Newest: 1.5. QoQ: 1.2 (index 1). YoY: 0.9 (index 4).
    # QoQ growth: ((1.5 - 1.2) / 1.2) * 100 = 25%
    # YoY growth: ((1.5 - 0.9) / 0.9) * 100 = 66.7%
    assert yoy == pytest.approx(66.666, 0.01)
    assert qoq == pytest.approx(25.0, 0.01)

@patch("app.canslim.yf.Ticker")
def test_evaluate_annual_and_roe(mock_ticker, sample_financials_df, sample_balance_sheet_df):
    mock_instance = MagicMock()
    mock_instance.financials = sample_financials_df
    mock_instance.balance_sheet = sample_balance_sheet_df
    mock_ticker.return_value = mock_instance
    
    screener = CanslimScreener(data_fetcher=None)
    passed, roe, reasons = screener.evaluate_annual_and_roe("AAPL")
    
    # eps_values = [5.0, 4.0, 3.0, 2.0]
    # YoY annual growth: (5-4)/4 = 25%, (4-3)/3 = 33.3%, (3-2)/2 = 50%. All >= 20%.
    # ROE: net_income (5.0) / stockholders equity (100000.0) * 100 = 0.005%.
    # Since ROE is < 17%, it should fail.
    assert not passed
    assert roe == pytest.approx(0.005)
    assert any("ROE" in r for r in reasons)

def test_calculate_relative_strength(mock_fetcher):
    screener = CanslimScreener(data_fetcher=mock_fetcher)
    tickers = ["AAPL", "MSFT", "GOOGL"]
    
    rs_results = screener.calculate_relative_strength(tickers)
    
    assert len(rs_results) == 3
    assert "AAPL" in rs_results
    assert 1 <= rs_results["AAPL"][1] <= 99

def test_check_market_direction(mock_fetcher):
    screener = CanslimScreener(data_fetcher=mock_fetcher)
    us_uptrend, kr_uptrend = screener._check_market_direction()
    
    # Since our sample stock DF has an upward trending linear price, both SMAs should hold true
    assert us_uptrend
    assert kr_uptrend

@patch("app.canslim.yf.Ticker")
def test_screen_watchlist(mock_ticker, mock_fetcher, sample_quarterly_financials_df, sample_financials_df, sample_balance_sheet_df):
    # Setup yfinance mock info
    mock_instance = MagicMock()
    mock_instance.quarterly_financials = sample_quarterly_financials_df
    mock_instance.financials = sample_financials_df
    mock_instance.balance_sheet = sample_balance_sheet_df
    # Mock high ROE to pass CANSLIM
    high_roe_bs = sample_balance_sheet_df.copy()
    high_roe_bs.loc["Stockholders Equity"] = [10.0, 8.0]
    mock_instance.balance_sheet = high_roe_bs
    mock_instance.info = {
        "longName": "Apple Inc.",
        "institutionalPercentHeld": 0.65
    }
    mock_ticker.return_value = mock_instance
    
    # Force high volume on the last day of the historical data to pass S criteria
    stock_df = mock_fetcher.fetch_historical_prices.return_value.copy()
    stock_df.iloc[-1, stock_df.columns.get_loc("Volume")] = 1000000
    # Ensure the price increased on the last day as well
    stock_df.iloc[-1, stock_df.columns.get_loc("Close")] = stock_df.iloc[-2, stock_df.columns.get_loc("Close")] * 1.03
    mock_fetcher.fetch_historical_prices.return_value = stock_df
    
    screener = CanslimScreener(data_fetcher=mock_fetcher)
    results = screener.screen_watchlist(["AAPL"])
    
    assert len(results) == 1
    # Check score properties
    score = results[0]
    assert score["symbol"] == "AAPL"
    assert score["passed_screener"]  # Should pass with all metrics green!
