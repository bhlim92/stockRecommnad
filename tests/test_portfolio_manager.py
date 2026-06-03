import pytest
import json
import os
from unittest.mock import patch
from app.portfolio_manager import PortfolioManager

def test_load_and_validate_portfolio(mock_portfolio_json):
    pm = PortfolioManager(mock_portfolio_json)
    data = pm.load_portfolio()
    
    assert data["cash"] == 10000000.0
    assert len(data["holdings"]) == 2
    assert data["target_allocation"]["stock"] == 0.6

def test_validate_portfolio_missing_fields(tmp_path):
    invalid_data = {
        "cash": 1000.0,
        "holdings": []
        # Missing target_allocation
    }
    file_path = tmp_path / "invalid_portfolio.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(invalid_data, f)
        
    pm = PortfolioManager(str(file_path))
    with pytest.raises(ValueError) as exc:
        pm.load_portfolio()
    assert "target_allocation" in str(exc.value)

def test_validate_portfolio_weights_not_1(tmp_path):
    invalid_data = {
        "cash": 1000.0,
        "holdings": [],
        "target_allocation": {
            "stock": 0.5,
            "bond": 0.2,
            "commodity": 0.1,
            "cash": 0.1  # Sums to 0.9, not 1.0
        }
    }
    file_path = tmp_path / "invalid_weights.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(invalid_data, f)
        
    pm = PortfolioManager(str(file_path))
    with pytest.raises(ValueError) as exc:
        pm.load_portfolio()
    assert "must sum to 1.0" in str(exc.value)

def test_get_asset_currency():
    pm = PortfolioManager("dummy.json")
    assert pm._get_asset_currency("005930.KS") == "KRW"
    assert pm._get_asset_currency("AAPL") == "USD"
    assert pm._get_asset_currency("GLD") == "USD"

def test_evaluate_and_rebalance_no_drift(mock_portfolio_json):
    pm = PortfolioManager(mock_portfolio_json)
    
    # Set prices such that actual weights exactly match target weights.
    # Total portfolio value target: stock=0.6, bond=0.2, commodity=0.1, cash=0.1.
    # Let's say Total Value = 20,000,000 KRW.
    # Cash = 10,000,000 KRW. Wait, target cash is 0.1 (10%), so Total Value should be 100,000,000 KRW if cash is 10,000,000.
    # If Total Value = 100,000,000 KRW:
    # Cash = 10,000,000 (10%)
    # Stock target = 60,000,000 (60%).
    # Bond target = 20,000,000 (20%).
    # Commodity target = 10,000,000 (10%).
    #
    # We have 100 shares of 005930.KS @ 70,000 KRW = 7,000,000 KRW.
    # We have 10 shares of AAPL @ 180 USD (x 1350 KRW/USD) = 2,430,000 KRW.
    # Total Stock Value = 9,430,000 KRW.
    # Total value = 19,430,000 KRW.
    # Let's set prices to make actual weights match targets, or just test drift trigger.
    
    current_prices = {
        "005930.KS": 70000.0,
        "AAPL": 180.0,
        "USDKRW=X": 1350.0
    }
    
    res = pm.evaluate_and_rebalance(current_prices)
    
    # Portfolio initial state:
    # Cash = 10,000,000 KRW
    # Stock = 9,430,000 KRW
    # Bond = 0
    # Commodity = 0
    # Total Value = 19,430,000 KRW.
    #
    # Actual weights:
    # Stock = 9.43M / 19.43M = 48.5% (target 60%, diff = -11.5%) -> Drift triggered!
    # Bond = 0% (target 20%, diff = -20%) -> Drift triggered!
    # Commodity = 0% (target 10%, diff = -10%) -> Drift triggered!
    # Cash = 10M / 19.43M = 51.5% (target 10%, diff = +41.5%) -> Drift triggered!
    
    assert res["rebalance_triggered"] is True
    assert len(res["rebalance_actions"]) > 0

def test_evaluate_and_rebalance_perfect_balance(mock_portfolio_json, tmp_path):
    # Create portfolio that is perfectly balanced
    balanced_data = {
        "cash": 1000000.0, # 10%
        "holdings": [
            {
                "symbol": "005930.KS", # Stock: 6,000,000 KRW (60%)
                "name": "Samsung Electronics",
                "quantity": 100.0,
                "purchase_price": 60000.0,
                "asset_class": "stock"
            },
            {
                "symbol": "TLT", # Bond: 2,000,000 KRW (20%)
                "name": "TLT ETF",
                "quantity": 20.0,
                "purchase_price": 100000.0,
                "asset_class": "bond"
            },
            {
                "symbol": "GLD", # Commodity: 1,000,000 KRW (10%)
                "name": "Gold ETF",
                "quantity": 10.0,
                "purchase_price": 100000.0,
                "asset_class": "commodity"
            }
        ],
        "target_allocation": {
            "stock": 0.6,
            "bond": 0.2,
            "commodity": 0.1,
            "cash": 0.1
        }
    }
    file_path = tmp_path / "balanced_portfolio.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(balanced_data, f)
        
    pm = PortfolioManager(str(file_path))
    current_prices = {
        "005930.KS": 60000.0,
        "TLT": 100000.0,
        "GLD": 100000.0,
        "USDKRW=X": 1.0 # 1:1 exchange to keep it simple
    }
    
    res = pm.evaluate_and_rebalance(current_prices)
    assert res["rebalance_triggered"] is False
    # All actions should be HOLD
    for action in res["rebalance_actions"]:
        assert action["action"] == "HOLD"
        assert action["suggested_qty_delta"] == 0.0
