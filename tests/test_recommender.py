import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from app.recommender import RecommendationEngine

@pytest.fixture
def sample_market_data():
    dates = [pd.Timestamp("2026-05-30"), pd.Timestamp("2026-05-31")]
    macro_df = pd.DataFrame({"Value": [3.1, 3.2]}, index=dates)
    yields_df = pd.DataFrame({"Yield": [4.1, 4.15]}, index=dates)
    ex_df = pd.DataFrame({"Close": [1350.0, 1355.0]}, index=dates)
    return {
        "macro": {"CPI": macro_df},
        "yields": {"US10Y": yields_df},
        "exchange_rates": {"USD_KRW": ex_df}
    }

@pytest.fixture
def sample_news():
    return [{
        "title": "Fed rate decision",
        "source": "Bloomberg",
        "pub_date": "Sun, 31 May 2026",
        "summary": "Fed kept interest rates constant."
    }]

@pytest.fixture
def sample_youtube():
    return [{
        "title": "Stock market trends",
        "channel_handle": "@wowtv",
        "published_at": "2026-05-31",
        "link": "https://youtube.com/123",
        "llm_summary": "Expert outlook is bullish."
    }]

@pytest.fixture
def sample_canslim():
    return [{
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "passed_screener": True,
        "rs_score": 0.85,
        "rs_rank": 88,
        "eps_growth_yoy": 25.0,
        "eps_growth_qoq": 30.0,
        "reasons": []
    }]

@pytest.fixture
def sample_portfolio_eval():
    return {
        "total_value": 20000000.0,
        "holdings_eval": [{
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "asset_class": "stock",
            "quantity": 10.0,
            "purchase_value": 2400000.0,
            "current_price": 180.0,
            "current_value": 2430000.0,
            "unrealized_pnl": 30000.0,
            "actual_weight": 0.1215
        }],
        "rebalance_actions": [{
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "asset_class": "stock",
            "current_qty": 10.0,
            "current_value": 2430000.0,
            "target_value": 12000000.0,
            "difference": 9570000.0,
            "action": "BUY",
            "suggested_qty_delta": 39.0
        }],
        "rebalance_triggered": True
    }

@patch("app.recommender.genai.GenerativeModel")
def test_generate_recommendation_report_success(
    mock_generative_model,
    sample_market_data,
    sample_news,
    sample_youtube,
    sample_canslim,
    sample_portfolio_eval
):
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "# Mock Investment Report\n\n- Regime: Bull Market\n- Action: Rebalance"
    mock_model_instance.generate_content.return_value = mock_response
    mock_generative_model.return_value = mock_model_instance
    
    engine = RecommendationEngine(api_key="mock-key")
    report = engine.generate_recommendation_report(
        market=sample_market_data,
        news=sample_news,
        youtube=sample_youtube,
        canslim=sample_canslim,
        portfolio=sample_portfolio_eval
    )
    
    assert "Mock Investment Report" in report
    assert "Regime" in report
    mock_model_instance.generate_content.assert_called_once()

def test_generate_recommendation_report_missing_key(
    sample_market_data,
    sample_news,
    sample_youtube,
    sample_canslim,
    sample_portfolio_eval
):
    # Initializes without key, checks fallback template
    engine = RecommendationEngine(api_key="")
    report = engine.generate_recommendation_report(
        market=sample_market_data,
        news=sample_news,
        youtube=sample_youtube,
        canslim=sample_canslim,
        portfolio=sample_portfolio_eval
    )
    
    assert "Daily Recommendation Report" in report
    assert "Warning: Bypassed due to missing Gemini API key" in report
