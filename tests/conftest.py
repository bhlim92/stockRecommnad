import pytest
import os

# Set mock env vars before any other modules load
os.environ["GEMINI_API_KEY"] = "mock-gemini-key"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "mock-credentials.json"
os.environ["GOOGLE_DRIVE_FOLDER_ID"] = "mock-folder-id"
os.environ["GOOGLE_DRIVE_TOKEN_JSON"] = ""
os.environ["TESTING"] = "true"

import json
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

# Ensure we don't pick up real env keys during test run
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "mock-credentials.json")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "mock-folder-id")
    monkeypatch.setenv("GOOGLE_DRIVE_TOKEN_JSON", "")
    monkeypatch.setenv("TESTING", "true")

@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    # Speeds up retry tests by bypassing time.sleep calls
    monkeypatch.setattr("time.sleep", lambda seconds: None)

@pytest.fixture
def mock_portfolio_json(tmp_path):
    portfolio_data = {
        "cash": 10000000.0,
        "base_currency": "KRW",
        "holdings": [
            {
                "symbol": "005930.KS",
                "name": "Samsung Electronics",
                "quantity": 100.0,
                "purchase_price": 70000.0,
                "asset_class": "stock"
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "quantity": 10.0,
                "purchase_price": 180.0,
                "asset_class": "stock"
            }
        ],
        "target_allocation": {
            "stock": 0.6,
            "bond": 0.2,
            "commodity": 0.1,
            "cash": 0.1
        }
    }
    file_path = tmp_path / "portfolio.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(portfolio_data, f)
    return str(file_path)

@pytest.fixture
def sample_stock_df():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=250, freq="B")
    # Generates a realistic upward trend to pass tests
    prices = np.linspace(100, 150, 250) + np.random.normal(0, 2, 250)
    volumes = np.random.randint(50000, 150000, 250)
    df = pd.DataFrame({
        "Open": prices - 1,
        "High": prices + 1,
        "Low": prices - 2,
        "Close": prices,
        "Volume": volumes
    }, index=dates)
    return df

@pytest.fixture
def sample_financials_df():
    # Columns are dates (newest first)
    dates = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31"), pd.Timestamp("2022-12-31")]
    # Basic EPS showing > 20% growth year-over-year
    eps_values = [5.0, 4.0, 3.0, 2.0]
    df = pd.DataFrame(
        [eps_values],
        index=["Basic EPS"],
        columns=dates
    )
    return df

@pytest.fixture
def sample_quarterly_financials_df():
    dates = [pd.Timestamp("2026-03-31"), pd.Timestamp("2025-12-31"), pd.Timestamp("2025-09-30"), pd.Timestamp("2025-06-30"), pd.Timestamp("2025-03-31")]
    eps_values = [1.5, 1.2, 1.1, 1.0, 0.9]
    df = pd.DataFrame(
        [eps_values],
        index=["Basic EPS"],
        columns=dates
    )
    return df

@pytest.fixture
def sample_balance_sheet_df():
    dates = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]
    equity_values = [100000.0, 80000.0]
    df = pd.DataFrame(
        [equity_values],
        index=["Stockholders Equity"],
        columns=dates
    )
    return df
