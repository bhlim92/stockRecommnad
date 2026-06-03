import pytest
from unittest.mock import patch, MagicMock
from app.gspread_fetcher import fetch_portfolio_holdings

SAMPLE_CSV = """투자금액비중,보유,Ticker,설명,,yahoo,google,현재가격,적정가격,25년 적정 EPS,25년 적정 PER,Fwd PER,적정 PER,목표값-최대,목표값-평균,목표값-중앙,목표값-분석가 의견합 ,구매가,투자금액,평가금액,수익,수익률,상승여력,비중
0.00%,0,AAPL,Apple Inc.,AAPL,,NASDAQ:,$315.20,,,,,,,$252.73,,,$209.87,$0.00,$0.00,$0.00,#DIV/0!,-19.82%,0.00%
5.81%,5.5,JPM,JP Morgan Chase & Co.,JPM,,NYSE:,$300.96,,,,,,,$342.96,,,$287.93,"$1,583.62","$1,655.28",$71.67,4.53%,13.96%,5.81%
4.53%,5,000660.ks,SK Hynix,000660,.ks,KRX:,"236,000.00",,,#VALUE!,Deprecated. Use =FINANCE instead,,Deprecated. Use =FINANCE instead,"224,600.00",,,"374,321.00","1,871,605.00","1,180,000.00","-691,605.00",-36.95%,-4.83%,4.53%
"""

@patch("app.gspread_fetcher.get_google_credentials")
@patch("app.gspread_fetcher.requests.get")
def test_fetch_portfolio_holdings(mock_get, mock_creds):
    # Set up mock credentials
    mock_credential_obj = MagicMock()
    mock_credential_obj.token = "mock-access-token"
    mock_creds.return_value = mock_credential_obj
    
    # Set up mock response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_CSV
    mock_get.return_value = mock_resp
    
    # Execute fetch
    holdings = fetch_portfolio_holdings()
    
    # Verify outputs
    assert len(holdings) == 2  # AAPL is filtered out since holdings == 0
    
    # Check JPM
    jpm = holdings[0]
    assert jpm["ticker"] == "JPM"
    assert jpm["name"] == "JP Morgan Chase & Co."
    assert jpm["quantity"] == 5.5
    assert jpm["current_price"] == 300.96
    assert jpm["purchase_price"] == 287.93
    assert jpm["total_purchase"] == 1583.62
    assert jpm["total_evaluation"] == 1655.28
    assert jpm["profit"] == 71.67
    assert jpm["roi"] == "4.53%"
    assert jpm["weight"] == "5.81%"
    
    # Check 000660.ks
    hynix = holdings[1]
    assert hynix["ticker"] == "000660.ks"
    assert hynix["name"] == "SK Hynix"
    assert hynix["quantity"] == 5.0
    assert hynix["current_price"] == 236000.0
    assert hynix["profit"] == -691605.0
    assert hynix["roi"] == "-36.95%"
