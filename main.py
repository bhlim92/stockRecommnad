import os
import argparse
import uvicorn
from datetime import datetime
from typing import Dict, List, Any

# Import application configuration and modules
from app.config import AppConfig
from app.utils.logger import setup_logger
from app.utils.helpers import get_date_n_days_ago
from app.data_fetcher import AssetDataFetcher
from app.news_fetcher import NewsFetcher
from app.youtube_summarizer import YouTubeSummarizer
from app.canslim import CanslimScreener
from app.portfolio_manager import PortfolioManager
from app.recommender import RecommendationEngine
from app.gdrive_uploader import GoogleDriveUploader

# Set up global logger
logger = setup_logger("orchestrator", AppConfig.LOG_FILE_PATH, AppConfig.LOG_LEVEL)

def main() -> None:
    # 1. Parse Command Line Arguments
    parser = argparse.ArgumentParser(description="Stock Discovery & Portfolio Rebalancing System Orchestrator")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Run the pipeline locally without uploading the generated report to Google Drive."
    )
    parser.add_argument(
        "--web", 
        action="store_true", 
        help="Start the FastAPI Web Server and Dashboard UI."
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to run the Web Server on (default: 8000)."
    )
    args = parser.parse_args()
    
    if args.web:
        logger.info(f"Starting Web Server on http://localhost:{args.port}...")
        uvicorn.run("app.web_server:app", host="127.0.0.1", port=args.port, reload=False)
        return
        
    if args.dry_run:
        logger.info("Executing pipeline in DRY-RUN mode. Google Drive upload will be bypassed.")
    else:
        logger.info("Executing pipeline in Standard mode. Generated report will be uploaded to Google Drive.")

    logger.info("Starting Daily Investment Pipeline execution...")

    # Load environmental watchlists if overridden in .env
    us_watchlist = os.getenv("US_WATCHLIST")
    kr_watchlist = os.getenv("KR_WATCHLIST")
    
    watchlist_us = [t.strip() for t in us_watchlist.split(",")] if us_watchlist else AppConfig.US_WATCHLIST
    watchlist_kr = [t.strip() for t in kr_watchlist.split(",")] if kr_watchlist else AppConfig.KR_WATCHLIST
    
    full_equity_watchlist = watchlist_us + watchlist_kr
    logger.info(f"Equity Watchlist: US ({len(watchlist_us)} tickers), KR ({len(watchlist_kr)} tickers)")

    # 2. Step 1: Initialize Data Fetcher and Ingest Market Data
    fetcher = AssetDataFetcher()
    market_data: Dict[str, Any] = {
        "prices": {},
        "yields": {},
        "macro": {},
        "exchange_rates": {}
    }

    # Fetch daily historical prices for watchlist equities (for RS and High calculations)
    logger.info("Ingesting historical price data for watchlist stocks...")
    for ticker in full_equity_watchlist:
        try:
            df = fetcher.fetch_historical_prices(ticker, period="1y", interval="1d")
            market_data["prices"][ticker] = df
        except Exception as e:
            logger.warning(f"Could not ingest price history for {ticker}: {str(e)}")

    # Fetch macro bond yields
    logger.info("Ingesting historical yield indicators...")
    for key, ticker in AppConfig.MACRO_TICKERS.items():
        if key in ["US10Y", "KR10YT=RR"] or "10Y" in key:
            try:
                df = fetcher.fetch_bond_yield(ticker, period="1y")
                market_data["yields"][key] = df
            except Exception as e:
                logger.warning(f"Could not ingest yield for {key} ({ticker}): {str(e)}")
        elif key == "USD_KRW" or ticker == "USDKRW=X":
            # Fetch USD/KRW Exchange Rate
            try:
                df = fetcher.fetch_historical_prices(ticker, period="1y")
                market_data["exchange_rates"]["USD_KRW"] = df
            except Exception as e:
                logger.warning(f"Could not fetch exchange rate {ticker}: {str(e)}")
        else:
            # Other macro commodities/indices tracked via prices (TLT, GLD, USO, DXY)
            try:
                df = fetcher.fetch_historical_prices(ticker, period="1y")
                market_data["prices"][key] = df
            except Exception as e:
                logger.warning(f"Could not fetch macro asset price for {key} ({ticker}): {str(e)}")

    # Fetch FRED Economic Indicators
    logger.info("Ingesting FRED macro-economic indicators...")
    three_years_ago = get_date_n_days_ago(365 * 3)
    for key, indicator_id in AppConfig.FRED_INDICATORS.items():
        try:
            df = fetcher.fetch_fred_indicator(indicator_id, start_date=three_years_ago)
            market_data["macro"][key] = df
        except Exception as e:
            logger.warning(f"Could not fetch FRED indicator {key} ({indicator_id}): {str(e)}")

    # 3. Step 2: Ingest Financial/Macro News
    logger.info("Fetching recent financial news...")
    news_fetcher = NewsFetcher()
    news_queries = ["S&P 500", "KOSPI", "US Federal Reserve interest rates", "inflation CPI", "US Treasury bond yields"]
    all_news: List[Dict[str, Any]] = []
    
    for query in news_queries:
        try:
            items = news_fetcher.fetch_query_news(query, limit=4)
            all_news.extend(items)
        except Exception as e:
            logger.warning(f"Could not fetch news for query '{query}': {str(e)}")
            
    # Remove duplicates by title
    seen_titles = set()
    unique_news = []
    for item in all_news:
        title_lower = item["title"].lower()
        if title_lower not in seen_titles:
            seen_titles.add(title_lower)
            unique_news.append(item)
    logger.info(f"Retrieved {len(unique_news)} unique news items.")

    # 4. Step 3: Extract and Summarize YouTube Video Transcripts
    logger.info("Extracting and summarizing YouTube expert channels...")
    pm = PortfolioManager(AppConfig.PORTFOLIO_FILE_PATH)
    try:
        portfolio_raw = pm.load_portfolio()
        selected_model = portfolio_raw.get("gemini_model", "gemini-3.5-flash")
    except Exception:
        selected_model = "gemini-3.5-flash"
    logger.info(f"Using Gemini AI Model: {selected_model}")
    yt_summarizer = YouTubeSummarizer(AppConfig.GEMINI_API_KEY, AppConfig.CHANNEL_ID_MAP, model_name=selected_model)
    youtube_summaries: List[Dict[str, Any]] = []
    videos_to_batch: List[Dict[str, Any]] = []

    for name, handle in AppConfig.YOUTUBE_CHANNELS.items():
        try:
            # 1. Resolve channel handle to ID
            channel_id = yt_summarizer.resolve_handle_to_id(handle)
            # 2. Get videos from last 48 hours
            videos = yt_summarizer.fetch_channel_videos_last_48h(channel_id)
            
            # Limit to at most 1 video per channel to conserve API quota
            if videos:
                videos = videos[:1]
            
            for video in videos:
                video_id = video["video_id"]
                title = video["title"]
                
                # 3. Fetch transcript (fallback to RSS description if unavailable)
                try:
                    content = yt_summarizer.get_transcript(video_id)
                except Exception:
                    logger.warning(f"Using RSS description fallback for video '{title}' ({video_id})")
                    content = video.get("description", "")
                    
                # If content is empty, use title as minimum text context
                if not content.strip():
                    content = f"Video Title: {title}. No description or transcript was available."
                
                videos_to_batch.append({
                    "video_id": video_id,
                    "title": title,
                    "channel_handle": handle,
                    "published_at": video["published_at"],
                    "link": video["link"],
                    "content": content
                })
        except Exception as e:
            logger.warning(f"Could not process YouTube channel {handle}: {str(e)}")

    # 4. Batch Summarize via Gemini (1 single request for all videos)
    if videos_to_batch:
        logger.info(f"Summarizing {len(videos_to_batch)} videos in a single batched call...")
        youtube_summaries = yt_summarizer.summarize_videos_batched(videos_to_batch)
    else:
        logger.info("No videos found to summarize.")

    logger.info(f"Summarized {len(youtube_summaries)} videos from YouTube expert channels.")

    # 5. Step 4: Generate Daily Investment Report via Gemini
    logger.info("Compiling daily investment report via Recommendation Engine...")
    recommender = RecommendationEngine(AppConfig.GEMINI_API_KEY, model_name=selected_model)
    
    report_markdown = recommender.generate_recommendation_report(
        market=market_data,
        news=unique_news,
        youtube=youtube_summaries
    )

    # 8. Step 7: Archive and Save locally
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    local_report_filename = f"reports/{timestamp}_report.md"
    
    try:
        with open(local_report_filename, "w", encoding="utf-8") as f:
            f.write(report_markdown)
        logger.info(f"Successfully archived generated report locally: {local_report_filename}")
    except Exception as e:
        logger.error(f"Failed to save report locally: {str(e)}")

    # 9. Step 8: Upload to Google Drive (if not dry run)
    if not args.dry_run:
        logger.info("Uploading report to Google Drive...")
        uploader = GoogleDriveUploader(
            credentials_path=AppConfig.GOOGLE_APPLICATION_CREDENTIALS,
            token_json_str=AppConfig.GOOGLE_DRIVE_TOKEN_JSON
        )
        try:
            uploader.authenticate()
            gdoc_link = uploader.upload_markdown_file(
                local_path=local_report_filename,
                filename=f"{timestamp}_Investment_Report",
                target_folder_name="Stock_Reports",
                folder_id=AppConfig.GOOGLE_DRIVE_FOLDER_ID
            )
            print("\n" + "="*80)
            print(f"Daily Pipeline executed successfully!")
            print(f"Google Drive Report Link: {gdoc_link}")
            print("="*80 + "\n")
            logger.info("Daily Pipeline completed with Google Drive upload.")
        except Exception as e:
            logger.error(f"Google Drive upload failed: {str(e)}")
            print("\n" + "="*80)
            print(f"Daily Pipeline executed, but Google Drive upload failed: {str(e)}")
            print(f"The report is available locally at: {local_report_filename}")
            print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("Daily Pipeline executed successfully in DRY-RUN mode!")
        print(f"The report has been saved locally at: {local_report_filename}")
        print("="*80 + "\n")
        logger.info("Daily Pipeline completed in DRY-RUN mode.")

if __name__ == "__main__":
    main()
