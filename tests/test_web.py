import os
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.web_server import app
from app.utils.tracker import tracker

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_tracker():
    tracker.reset()
    yield

def test_get_static_routes():
    # Verify index HTML route fetches successfully
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    # Verify style CSS route
    response = client.get("/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]

    # Verify script JS route
    response = client.get("/app.js")
    assert response.status_code == 200

def test_api_get_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "idle"
    assert data["progress"] == 0
    assert "logs" in data

@patch("app.web_server.threading.Thread")
def test_api_trigger_run_success(mock_thread):
    # Set to idle state
    tracker.status = "idle"
    
    response = client.post("/api/run")
    assert response.status_code == 200
    assert "triggered" in response.json()["message"]
    mock_thread.assert_called_once()

def test_api_trigger_run_already_executing():
    # Set to running state
    tracker.status = "ingesting"
    
    response = client.post("/api/run")
    assert response.status_code == 400
    assert "already executing" in response.json()["detail"]

def test_api_get_portfolio(mock_portfolio_json):
    with patch("app.web_server.AppConfig.PORTFOLIO_FILE_PATH", mock_portfolio_json):
        response = client.get("/api/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert data["cash"] == 10000000.0
        assert "target_allocation" in data

def test_api_update_portfolio_success(mock_portfolio_json):
    with patch("app.web_server.AppConfig.PORTFOLIO_FILE_PATH", mock_portfolio_json):
        payload = {
            "cash": 5000000.0,
            "base_currency": "KRW",
            "holdings": [],
            "target_allocation": {
                "stock": 0.4,
                "bond": 0.3,
                "commodity": 0.2,
                "cash": 0.1
            }
        }
        response = client.post("/api/portfolio", json=payload)
        assert response.status_code == 200
        assert "updated successfully" in response.json()["message"]
        
        # Verify saved data
        with open(mock_portfolio_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["cash"] == 5000000.0
            assert data["target_allocation"]["stock"] == 0.4

def test_api_update_portfolio_invalid_weight(mock_portfolio_json):
    with patch("app.web_server.AppConfig.PORTFOLIO_FILE_PATH", mock_portfolio_json):
        payload = {
            "cash": 5000000.0,
            "base_currency": "KRW",
            "holdings": [],
            "target_allocation": {
                "stock": 0.8,
                "bond": 0.8, # total 1.6
                "commodity": 0.0,
                "cash": 0.0
            }
        }
        response = client.post("/api/portfolio", json=payload)
        assert response.status_code == 400
        assert "must sum exactly to 1.0" in response.json()["detail"]

def test_api_get_reports_list(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "2026-05-30_report.md").write_text("# Report 1")
    (reports_dir / "2026-05-31_report.md").write_text("# Report 2")
    
    with patch("app.web_server.os.path.exists", return_value=True), \
         patch("app.web_server.os.listdir", return_value=["2026-05-30_report.md", "2026-05-31_report.md"]):
        response = client.get("/api/reports")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # sorted reverse order
        assert data[0] == "2026-05-31_report.md"

def test_api_get_report_content(tmp_path):
    report_file = tmp_path / "2026-05-31_report.md"
    report_file.write_text("# Report Content Test")
    
    with patch("app.web_server.os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="# Report Content Test")))))):
        response = client.get("/api/reports/2026-05-31_report.md")
        assert response.status_code == 200
        assert response.json()["content"] == "# Report Content Test"

def test_api_get_rebalance_strategy_not_found():
    with patch("app.web_server._get_latest_rebalance_strategy", return_value=None):
        response = client.get("/api/portfolio/rebalance")
        assert response.status_code == 200
        assert "아직 생성된 리밸런싱 전략이 없습니다" in response.json()["content"]

def test_api_get_rebalance_strategy_success():
    mock_strategy = {"filename": "2026-06-03_rebalance_strategy.md", "content": "# Rebalance Plan"}
    with patch("app.web_server._get_latest_rebalance_strategy", return_value=mock_strategy):
        response = client.get("/api/portfolio/rebalance")
        assert response.status_code == 200
        assert response.json()["filename"] == "2026-06-03_rebalance_strategy.md"
        assert response.json()["content"] == "# Rebalance Plan"

@patch("app.web_server.fetch_portfolio_holdings")
@patch("app.web_server._get_latest_recommendation_report")
@patch("app.scoring.QuantScorer")
@patch("google.generativeai.GenerativeModel")
def test_api_generate_rebalance_strategy_success(mock_model_class, mock_quant_scorer_class, mock_get_report, mock_fetch_holdings):
    mock_fetch_holdings.return_value = [
        {"ticker": "005930.KS", "name": "Samsung", "quantity": 10.0, "current_price": 70000.0, "purchase_price": 68000.0, "total_purchase": 680000.0, "total_evaluation": 700000.0, "profit": 20000.0, "roi": "2.94%", "weight": "100.0%"}
    ]
    mock_get_report.return_value = {"filename": "2026-06-03_report.md", "content": "Recommend: Buying Tech"}
    
    mock_scorer_instance = MagicMock()
    mock_scorer_instance.calculate_scores.return_value = {
        "005930.KS": {
            "symbol": "005930.KS",
            "name": "Samsung",
            "entry_score": 80,
            "entry_details": ["현재가 > 5일선"],
            "eval_score": 90,
            "eval_details": ["PER 저평가"],
            "fundamentals": {"per": 15.0, "peg": 1.0, "eps": 5000.0, "fwd_eps": 5500.0, "target_price": 85000.0},
            "moving_averages": {"sma_5": 70000.0, "sma_20": 68000.0, "sma_200": 65000.0},
            "volume": {"current": 15000000.0, "avg_20": 12000000.0}
        }
    }
    mock_quant_scorer_class.return_value = mock_scorer_instance
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = MagicMock(text="AI Rebalance Strategy Content")
    mock_model_class.return_value = mock_model
    
    with patch("builtins.open", MagicMock()), \
         patch("app.web_server.os.makedirs"), \
         patch("app.web_server.os.path.exists", return_value=False):
        
        payload = {"api_key": "fake_key", "model": "gemini-2.5-flash"}
        response = client.post("/api/portfolio/rebalance", json=payload)
        assert response.status_code == 200
        assert "rebalance_strategy.md" in response.json()["filename"]
        assert response.json()["content"] == "AI Rebalance Strategy Content"
