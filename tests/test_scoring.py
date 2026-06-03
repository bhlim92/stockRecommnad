import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from app.scoring import QuantScorer

@patch("app.scoring.yf.Ticker")
def test_quant_scorer_calculate_scores(mock_yf_ticker, sample_stock_df):
    # Setup mocks
    # Force last price to be exactly 150.0 to make evaluation score deterministic
    sample_stock_df.loc[sample_stock_df.index[-1], "Close"] = 150.0
    
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.info = {
        "shortName": "Apple Inc.",
        "trailingPE": 10.0, # max score 30
        "pegRatio": 1.0, # max score 20
        "trailingEps": 5.0,
        "forwardEps": 6.5, # (6.5-5.0)/5.0 = 30% growth (>=20%) => max score 20
        "targetMeanPrice": 180.0, # (180-150)/150 = 20% upside => max score 15
        "passed_screener": True, # max score 15
    }
    mock_yf_ticker.return_value = mock_ticker_instance

    scorer = QuantScorer()
    
    # Calculate scores for AAPL with preloaded prices
    results = scorer.calculate_scores(["AAPL"], preloaded_prices={"AAPL": sample_stock_df})
    
    assert "AAPL" in results
    aapl_result = results["AAPL"]
    
    assert aapl_result["name"] == "Apple Inc."
    assert aapl_result["current_price"] == 150.0
    
    # Verify values
    # Total score should be 100 based on weight logic (30 + 20 + 20 + 15 + 15 = 100)
    assert aapl_result["eval_score"] == 100
