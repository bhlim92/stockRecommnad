import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_app_version() -> str:
    version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return os.getenv("APP_VERSION", "3.4")

class AppConfig:
    APP_VERSION: str = get_app_version()
    # API credentials
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    GOOGLE_DRIVE_TOKEN_JSON: str = os.getenv("GOOGLE_DRIVE_TOKEN_JSON", "")
    PORTFOLIO_SPREADSHEET_ID: str = os.getenv("PORTFOLIO_SPREADSHEET_ID", "19Gtw2QutX6xChSDanqd79edD3WFYVqooeRiHsK8pGdI")
    PORTFOLIO_SPREADSHEET_GID: str = os.getenv("PORTFOLIO_SPREADSHEET_GID", "1126172231")
    
    # Execution parameters
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "logs/app.log")
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", "5242880"))
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    PORTFOLIO_FILE_PATH: str = os.getenv("PORTFOLIO_FILE_PATH", "portfolio.json")
    
    # Watchlists (Default)
    US_WATCHLIST: list[str] = [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "LLY", "AVGO", "COST"
    ]
    KR_WATCHLIST: list[str] = [
        "005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", 
        "068270.KS", "005490.KS", "051910.KS", "035420.KS", "000270.KS"
    ]
    
    # Macro tickers tracked via yfinance
    MACRO_TICKERS: dict[str, str] = {
        "DXY": "DX-Y.NYB",          # Dollar Index
        "US10Y": "^TNX",            # US 10Y Treasury Yield
        "TLT": "TLT",               # US Treasury Long Bond ETF
        "GLD": "GLD",               # Gold ETF
        "USO": "USO",               # WTI Crude Oil ETF
        "USD_KRW": "USDKRW=X"       # USD/KRW Exchange Rate
    }
    
    # FRED Macro Indicator IDs tracked via FinanceDataReader
    FRED_INDICATORS: dict[str, str] = {
        "CPI": "CPIAUCSL",              # US CPI
        "FED_RATE": "FEDFUNDS",         # US Fed Funds Rate
        "UNEMPLOYMENT": "UNRATE",       # US Unemployment Rate
        "GDP_GROWTH": "A191RL1Q225SBEA", # US Real GDP Quarterly Growth Rate
        "KR_BASE_RATE": "INTDSRKRM193N", # KR Base Interest Rate (from FRED)
        "KR_CPI": "KORCPIALLMINMEI"      # KR CPI (from FRED)
    }
    
    # YouTube channel handles to search
    YOUTUBE_CHANNELS: dict[str, str] = {
        "wowtv": "@hkwowtv",
        "orlando": "@orlandocampus",
        "3protv": "@3protv",
        "sosumonkey": "@sosumonkey",
        "lucky_tv": "@lucky_tv",
        "talent": "@talentinvestment",
        "profhalf": "@profhalf",
        "softdragon": "@softdragon",
        "kang": "@강환국",
    }

    # Pre-resolved Channel ID Map (verified working RSS status 200)
    CHANNEL_ID_MAP: dict[str, str] = {
        "@hkwowtv": "UCF8AeLlUbEpKju6v1H6p8Eg",
        "@orlandocampus": "UCwSSqi-s0wcH6pJbH3YPZqQ",
        "@3protv": "UChlv4GSd7OQl3js-jkLOnFA",
        "@sosumonkey": "UCC3yfxS5qC6PCwDzetUuEWg",
        "@lucky_tv": "UCvil4OAt-zShzkKHsg9EQAw",
        "@talentinvestment": "UCBM86JVoHLqg9irpR2XKvGw",
        "@profhalf": "UCczff_dQVVb9sSEULFUJ-sw",
        "@softdragon": "UCSPMRoAphbObUYeDaX367Fg",
        "@강환?: "UCSWPuzlD337Y6VBkyFPwT8g"
    }
