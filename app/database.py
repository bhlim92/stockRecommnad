import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Setup database logger
logger = logging.getLogger("database")

Base = declarative_base()

class ScreenerResult(Base):
    __tablename__ = 'screener_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String(20), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    current_price = Column(Float, nullable=True)
    entry_score = Column(Integer, nullable=True)
    eval_score = Column(Integer, nullable=True)
    total_score = Column(Integer, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

# Database Engine initialization
engine = None
SessionLocal = None

def get_db_url() -> str:
    db_type = os.getenv("DB_TYPE", "").lower()
    # Fallback to sqlite if DB_TYPE is not set or empty
    if not db_type:
        if os.getenv("TESTING", "").lower() == "true":
            return ""
        db_type = "sqlite"
    
    db_name = os.getenv("DB_NAME", "")
    
    if db_type == "sqlite":
        db_file = db_name if db_name else "stock_db.sqlite"
        # If relative filename (no directories), put it in the project's data directory
        if not os.path.isabs(db_file) and "/" not in db_file and "\\" not in db_file:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(root_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_file = os.path.join(data_dir, db_file)
        abs_path = os.path.abspath(db_file).replace("\\", "/")
        return f"sqlite:///{abs_path}"
    
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306" if db_type == "mariadb" else "5432")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    
    if not user or not db_name:
        logger.warning("Database configuration missing username or database name. DB integration disabled.")
        return ""
        
    if db_type == "mariadb" or db_type == "mysql":
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"
    elif db_type == "postgresql":
        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    logger.warning(f"Unsupported database type: {db_type}. DB integration disabled.")
    return ""

def init_db():
    global engine, SessionLocal
    db_url = get_db_url()
    if not db_url:
        return False
        
    try:
        # Prevent PyMySQL encoding issues with MariaDB by using safe parameters
        if "mysql+pymysql" in db_url:
            engine = create_engine(db_url, pool_recycle=3600, pool_pre_ping=True)
        else:
            engine = create_engine(db_url, pool_pre_ping=True)
            
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Database successfully connected and tables verified.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        engine = None
        SessionLocal = None
        return False

# Trigger initialization on module import
init_db()

def save_screener_results(market: str, results: List[Dict[str, Any]]) -> bool:
    """Saves all non-empty results to the configured RDBMS in a bulk insert."""
    global SessionLocal
    if SessionLocal is None:
        # Try to reinitialize in case configuration changed at runtime
        if not init_db():
            return False
            
    try:
        db = SessionLocal()
        db_records = []
        
        # Find the scan start time from the results to ensure all records share the exact same timestamp
        scan_time = None
        for item in results:
            if item.get("created_at") and item["created_at"] != "-":
                try:
                    scan_time = datetime.strptime(item["created_at"], "%Y-%m-%d %H:%M:%S")
                    break
                except Exception:
                    pass
                    
        if not scan_time:
            scan_time = datetime.utcnow()
        
        for item in results:
            # Only save items that have been actually analyzed (score not None)
            if item.get("total_score") is not None:
                record = ScreenerResult(
                    market=market,
                    symbol=item["symbol"],
                    name=item["name"],
                    current_price=item.get("current_price"),
                    entry_score=item.get("entry_score"),
                    eval_score=item.get("eval_score"),
                    total_score=item.get("total_score"),
                    rationale=item.get("rationale"),
                    created_at=scan_time
                )
                db_records.append(record)
                
        if db_records:
            db.bulk_save_objects(db_records)
            db.commit()
            logger.info(f"Successfully saved {len(db_records)} screener results for {market} to the database.")
            db.close()
            return True
            
        db.close()
        return False
    except Exception as e:
        logger.error(f"Error during saving screener results to database: {str(e)}")
        return False

def get_top_screener_results(limit: int = 10, market: str = None) -> List[Dict[str, Any]]:
    """Retrieve the latest top screener results sorted by total_score."""
    global SessionLocal
    if SessionLocal is None:
        if not init_db():
            return []
    try:
        db = SessionLocal()
        # Find the latest scan time
        query = db.query(ScreenerResult)
        if market:
            query = query.filter(ScreenerResult.market == market)
            
        latest_record = query.order_by(ScreenerResult.created_at.desc()).first()
        if not latest_record:
            db.close()
            return []
            
        latest_time = latest_record.created_at
        
        # Query results from that scan time
        res_query = db.query(ScreenerResult).filter(ScreenerResult.created_at == latest_time)
        if market:
            res_query = res_query.filter(ScreenerResult.market == market)
            
        results = res_query.order_by(ScreenerResult.total_score.desc()).limit(limit).all()
        
        dict_results = []
        for r in results:
            dict_results.append({
                "market": r.market,
                "symbol": r.symbol,
                "name": r.name,
                "current_price": r.current_price,
                "entry_score": r.entry_score,
                "eval_score": r.eval_score,
                "total_score": r.total_score,
                "rationale": r.rationale,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
            })
        db.close()
        return dict_results
    except Exception as e:
        logger.error(f"Error retrieving top screener results: {str(e)}")
        return []

def get_latest_score_by_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent score for a specific ticker symbol."""
    global SessionLocal
    if SessionLocal is None:
        if not init_db():
            return None
    try:
        db = SessionLocal()
        symbol_upper = symbol.upper()
        # Find latest record for this exact symbol (or matching the prefix if exact fails, though usually exact)
        record = db.query(ScreenerResult).filter(
            ScreenerResult.symbol == symbol_upper
        ).order_by(ScreenerResult.created_at.desc()).first()
        
        if not record:
            # Fallback for Yahoo format mapping if they omitted suffix
            record = db.query(ScreenerResult).filter(
                ScreenerResult.symbol.startswith(symbol_upper)
            ).order_by(ScreenerResult.created_at.desc()).first()
            
        if not record:
            db.close()
            return None
            
        res = {
            "market": record.market,
            "symbol": record.symbol,
            "name": record.name,
            "current_price": record.current_price,
            "entry_score": record.entry_score,
            "eval_score": record.eval_score,
            "total_score": record.total_score,
            "rationale": record.rationale,
            "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else ""
        }
        db.close()
        return res
    except Exception as e:
        logger.error(f"Error retrieving score for {symbol}: {str(e)}")
        return None

