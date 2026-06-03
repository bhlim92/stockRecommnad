# Stock Discovery & Portfolio Rebalancing System

An automated, daily investment recommendation system that crawls financial data (stocks, bonds, commodities, currencies, macro indicators), gathers recent financial news and expert YouTube videos, screens equities using the **CANSLIM** strategy, analyzes current portfolio drift, and generates a markdown report uploaded directly to Google Drive as an editable Google Doc.

---

## 1. Project Directory Structure

```text
stockRecommnad/
├── app/
│   ├── __init__.py
│   ├── config.py              # Application settings, watchlists, and YouTube cached IDs
│   ├── data_fetcher.py        # Wrappers for yfinance and FinanceDataReader
│   ├── news_fetcher.py        # RSS parser for Google News search queries
│   ├── youtube_summarizer.py  # YouTube RSS parse, transcript fetch, and Gemini summaries
│   ├── canslim.py             # CANSLIM growth stock screener logic
│   ├── recommender.py         # LLM prompt composer and report generator
│   ├── portfolio_manager.py   # Portfolio valuation, currency conversion, and rebalancing math
│   ├── gdrive_uploader.py     # Google Drive Service Account API connector
│   └── utils/
│       ├── __init__.py
│       ├── logger.py          # Rotating file logging configuration
│       └── helpers.py         # Retry decorator and datetime helpers
├── tests/                     # Offline unit and integration test suite
│   ├── conftest.py
│   ├── test_data_fetcher.py
│   ├── test_news_fetcher.py
│   ├── test_youtube_summarizer.py
│   ├── test_canslim.py
│   ├── test_portfolio_manager.py
│   ├── test_recommender.py
│   └── test_gdrive_uploader.py
├── .env.example               # Template for API keys and configuration
├── portfolio.json             # Current holdings database (JSON format)
├── requirements.txt           # Python packages required
├── run_pipeline.bat           # Daily automation script for Task Scheduler
├── deployment.md              # In-depth Deployment & Maintenance Plan
├── main.py                    # Application CLI Entrypoint orchestrator
└── README.md                  # This file
```

---

## 2. Setup & Getting Started

### Prerequisites
* **Python 3.10+** (Python 3.12 is recommended and pre-configured)
* **Google Cloud Project**:
  1. Enable the **Google Drive API**.
  2. Create a **Service Account** and download its credentials as a **JSON Key file**.
  3. Share your target Google Drive folder with the service account email (found in the JSON file) as an **Editor**.
* **Gemini API Key**: Retrieve your API key from Google AI Studio.

### Step 1: Clone and Configure Environment
1. In the project root, copy `.env.example` to `.env`:
   ```cmd
   copy .env.example .env
   ```
2. Open `.env` and fill in your keys and paths:
   ```env
   GEMINI_API_KEY="your-gemini-api-key"
   GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\your\google-service-account.json"
   GOOGLE_DRIVE_FOLDER_ID="your-target-google-drive-folder-id"
   ```

### Step 2: Initialize Portfolio Database
Configure your initial holdings, base currency, and target asset allocation weights in [portfolio.json](file:///c:/Users/samsung/proj/stockRecommnad/portfolio.json):
```json
{
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
```

---

## 3. Running the System

### Run Locally (Dry Run Mode)
Dry run compiles the entire daily report, runs CANSLIM metrics, evaluates rebalancing actions, and outputs the report locally to a file under `reports/` **without** uploading to Google Drive or modifying your portfolio database. This is ideal for testing:
```bash
python main.py --dry-run
```

### Run Production Mode
Production mode fetches live data, runs rebalancing math, creates the report, and uploads it to Google Drive as an editable Google Doc:
```bash
python main.py
```

### Run Automated Tests
Execute the offline test suite using pytest to verify calculations and scrapers are functioning properly:
```bash
python -m pytest tests/
```

---

## 4. Daily Automation (Windows Task Scheduler)

You can automate execution to run every day at e.g., 6:00 AM using `run_pipeline.bat`:

1. Open **Windows Task Scheduler** (`taskschd.msc`).
2. Click **Create Basic Task** and set:
   * **Trigger**: *Daily* (e.g. 6:00 AM).
   * **Action**: *Start a program*.
   * **Program/script**: `c:\Users\samsung\proj\stockRecommnad\run_pipeline.bat`
   * **Start in**: `c:\Users\samsung\proj\stockRecommnad` (Required!)
3. Under task properties, select **Run whether user is logged on or not** and check **Run with highest privileges**.
4. Execution logs will accumulate under `logs/scheduler.log` and rotating program traces under `logs/app.log`.

For detailed troubleshooting procedures, logging parameters, and recovery steps when third-party APIs change, see the [deployment.md](file:///c:/Users/samsung/proj/stockRecommnad/deployment.md) guide.
