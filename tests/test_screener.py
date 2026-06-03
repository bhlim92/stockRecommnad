import os
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pandas as pd

from app.web_server import app
from app.screener import ScreenerManager

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_screener_manager():
    screener = ScreenerManager()
    screener._init_screener()
    yield
    screener._init_screener()

def test_screener_static_route():
    # Verify screener HTML route fetches successfully
    response = client.get("/screener.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@patch("app.screener.ScreenerManager._run_screener_worker")
def test_screener_start_success(mock_worker):
    payload = {"market": "sp500"}
    response = client.post("/api/screener/start", json=payload)
    assert response.status_code == 200
    assert response.json()["message"] == "Screener started"
    
    # Test status endpoint
    status_response = client.get("/api/screener/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] == "running"
    assert status_data["market"] == "sp500"

def test_screener_stop_not_running():
    response = client.post("/api/screener/stop")
    assert response.status_code == 400
    assert "Screener not running" in response.json()["detail"]

@patch("app.screener.ScreenerManager._run_screener_worker")
def test_screener_stop_running(mock_worker):
    # Set status to running
    screener = ScreenerManager()
    screener.state["status"] = "running"
    
    response = client.post("/api/screener/stop")
    assert response.status_code == 200
    assert response.json()["message"] == "Screener stop requested"
    assert screener.state["aborted"] is True

@patch("app.screener.requests.get")
@patch("app.screener.pd.read_html")
def test_screener_load_tickers_sp500(mock_read_html, mock_get):
    mock_resp = MagicMock()
    mock_resp.text = "<html></html>"
    mock_get.return_value = mock_resp
    
    mock_df = pd.DataFrame({"Symbol": ["AAPL", "MSFT", "BRK.B"], "Security": ["Apple Inc.", "Microsoft Corp.", "Berkshire Hathaway"]})
    mock_read_html.return_value = [mock_df]
    
    with patch("app.screener.os.path.exists", return_value=False), \
         patch("app.screener.os.makedirs"), \
         patch("builtins.open", MagicMock()):
        screener = ScreenerManager()
        tickers = screener._load_tickers("sp500")
        assert len(tickers) == 3
        assert tickers[0]["symbol"] == "AAPL"
        assert tickers[0]["name"] == "Apple Inc."
        assert tickers[2]["symbol"] == "BRK-B" # period replaced with hyphen

@patch("app.screener.fdr.StockListing")
def test_screener_load_tickers_kr(mock_fdr_listing):
    mock_df = pd.DataFrame({
        "Code": ["005930", "000660"],
        "Name": ["Samsung", "Hynix"],
        "Marcap": [400000000000000, 100000000000000]
    })
    mock_fdr_listing.return_value = mock_df
    
    with patch("app.screener.os.path.exists", return_value=False), \
         patch("app.screener.os.makedirs"), \
         patch("builtins.open", MagicMock()):
        screener = ScreenerManager()
        tickers = screener._load_tickers("kospi200")
        assert len(tickers) == 2
        assert tickers[0]["symbol"] == "005930.KS"
        assert tickers[0]["name"] == "Samsung"

# ==========================================
# New Ticker caching & API endpoints tests
# ==========================================

@patch("app.screener.ScreenerManager._load_tickers")
def test_api_get_tickers_no_cache(mock_load):
    mock_load.return_value = [{"symbol": "TEST1", "name": "Company1"}, {"symbol": "TEST2", "name": "Company2"}]
    with patch("app.web_server.os.path.exists", return_value=False):
        response = client.get("/api/tickers/sp500")
        assert response.status_code == 200
        assert response.json()["tickers"] == [{"symbol": "TEST1", "name": "Company1"}, {"symbol": "TEST2", "name": "Company2"}]
        mock_load.assert_called_once_with("sp500")

def test_api_get_tickers_invalid_market():
    response = client.get("/api/tickers/invalid_market")
    assert response.status_code == 400
    assert "Invalid market" in response.json()["detail"]

@patch("app.web_server.os.makedirs")
@patch("builtins.open")
def test_api_update_tickers_success(mock_open, mock_makedirs):
    payload = [{"symbol": "NEW1", "name": "New Company 1"}, {"symbol": "NEW2", "name": "New Company 2"}]
    response = client.put("/api/tickers/sp500", json=payload)
    assert response.status_code == 200
    assert "updated successfully" in response.json()["message"]
    assert response.json()["count"] == 2

@patch("app.screener.ScreenerManager._load_tickers")
def test_api_refresh_tickers(mock_load):
    mock_load.return_value = [{"symbol": "REFRESHED1", "name": "Refreshed Company 1"}, {"symbol": "REFRESHED2", "name": "Refreshed Company 2"}]
    response = client.post("/api/tickers/sp500/refresh")
    assert response.status_code == 200
    assert "refreshed successfully" in response.json()["message"]
    assert response.json()["tickers"] == [{"symbol": "REFRESHED1", "name": "Refreshed Company 1"}, {"symbol": "REFRESHED2", "name": "Refreshed Company 2"}]
    mock_load.assert_called_once_with("sp500", force_refresh=True)
