import os
import logging
from typing import List, Dict, Any
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
    if not db_type:
        return ""
    
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306" if db_type == "mariadb" else "5432")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "")
    
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
