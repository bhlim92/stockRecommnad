import os
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, ScreenerResult, save_screener_results

@pytest.fixture
def temp_db():
    # setup in-memory sqlite engine for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Patch SessionLocal inside app.database to use this in-memory test DB session
    with patch("app.database.SessionLocal", TestingSessionLocal):
        yield TestingSessionLocal
        
    Base.metadata.drop_all(bind=engine)

def test_save_screener_results_success(temp_db):
    results = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "current_price": 180.5,
            "entry_score": 85,
            "eval_score": 90,
            "total_score": 175,
            "rationale": "Perfect trend"
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corp.",
            "current_price": None, # Should support None
            "entry_score": None,   # Should filter out if total_score is None, but let's test with total_score defined
            "eval_score": 80,
            "total_score": 140,
            "rationale": "Steady growth"
        },
        {
            "symbol": "TSLA",
            "name": "Tesla Inc.",
            "current_price": None,
            "entry_score": None,
            "eval_score": None,
            "total_score": None, # This should be filtered out (skipped)
            "rationale": "Pending analysis"
        }
    ]
    
    success = save_screener_results("sp500", results)
    assert success is True
    
    # Query database and verify
    db = temp_db()
    records = db.query(ScreenerResult).all()
    assert len(records) == 2 # TSLA should have been filtered out because total_score is None
    
    # Check AAPL
    aapl_rec = db.query(ScreenerResult).filter(ScreenerResult.symbol == "AAPL").first()
    assert aapl_rec is not None
    assert aapl_rec.market == "sp500"
    assert aapl_rec.name == "Apple Inc."
    assert aapl_rec.current_price == 180.5
    assert aapl_rec.entry_score == 85
    assert aapl_rec.eval_score == 90
    assert aapl_rec.total_score == 175
    assert aapl_rec.rationale == "Perfect trend"
    assert aapl_rec.created_at is not None
    
    # Check MSFT
    msft_rec = db.query(ScreenerResult).filter(ScreenerResult.symbol == "MSFT").first()
    assert msft_rec is not None
    assert msft_rec.current_price is None
    assert msft_rec.total_score == 140
    
    # Both AAPL and MSFT should share the exact same fallback timestamp
    assert aapl_rec.created_at == msft_rec.created_at
    
    # TSLA should not exist
    tsla_rec = db.query(ScreenerResult).filter(ScreenerResult.symbol == "TSLA").first()
    assert tsla_rec is None
    
    db.close()

def test_save_screener_results_with_provided_timestamp(temp_db):
    results = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "total_score": 175,
            "created_at": "2026-06-03 10:00:00"
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corp.",
            "total_score": 140,
            "created_at": "2026-06-03 10:00:00"
        }
    ]
    
    success = save_screener_results("sp500", results)
    assert success is True
    
    db = temp_db()
    aapl_rec = db.query(ScreenerResult).filter(ScreenerResult.symbol == "AAPL").first()
    msft_rec = db.query(ScreenerResult).filter(ScreenerResult.symbol == "MSFT").first()
    
    assert aapl_rec is not None
    assert msft_rec is not None
    
    # Both records must share the exact same parsed datetime from the input
    assert aapl_rec.created_at == msft_rec.created_at
    assert aapl_rec.created_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-06-03 10:00:00"
    
    db.close()
