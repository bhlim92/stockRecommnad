import os
import json
import threading
import hmac
import hashlib
import time
import base64
import requests
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Body, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from app.config import AppConfig
from app.utils.tracker import tracker
from app.utils.logger import setup_logger
from app.utils.helpers import get_date_n_days_ago
from app.data_fetcher import AssetDataFetcher
from app.news_fetcher import NewsFetcher
from app.youtube_summarizer import YouTubeSummarizer
from app.canslim import CanslimScreener
from app.portfolio_manager import PortfolioManager
from app.recommender import RecommendationEngine
from app.gdrive_uploader import GoogleDriveUploader
from app.gspread_fetcher import fetch_portfolio_holdings
from app.screener import ScreenerManager

logger = setup_logger("web_server", AppConfig.LOG_FILE_PATH, AppConfig.LOG_LEVEL)

# Session configurations
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "antigravity-quant-secret-2026-key")
AUTHORIZED_EMAIL = "bumhyun.lim@gmail.com"
TESTING = os.getenv("TESTING", "false").lower() == "true"

def generate_session_token(email: str) -> str:
    # 30 days expiry
    expiry = int(time.time()) + 30 * 24 * 60 * 60
    payload = f"{email}:{expiry}"
    signature = hmac.new(AUTH_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = f"{payload}:{signature}"
    return base64.b64encode(token.encode()).decode()

def verify_session_token(token_b64: str) -> Optional[str]:
    try:
        token = base64.b64decode(token_b64.encode()).decode()
        parts = token.split(":")
        if len(parts) != 3:
            return None
        email, expiry, signature = parts[0], parts[1], parts[2]
        
        # Verify signature
        payload = f"{email}:{expiry}"
        expected_sig = hmac.new(AUTH_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
            
        # Verify expiry
        if int(expiry) < time.time():
            return None
            
        return email
    except Exception:
        return None

def get_google_client_id() -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if client_id:
        return client_id
        
    token_json_str = os.getenv("GOOGLE_DRIVE_TOKEN_JSON", "")
    if token_json_str:
        try:
            token_data = json.loads(token_json_str)
            cid = token_data.get("client_id", "")
            if cid:
                return cid
        except Exception:
            pass
            
    credentials_path = "config/credentials.json"
    if os.path.exists(credentials_path):
        try:
            with open(credentials_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in ["installed", "web"]:
                    if key in data:
                        cid = data[key].get("client_id", "")
                        if cid:
                            return cid
        except Exception:
            pass
            
    return "412232683452-rpuer01djkv705i304dc99l6u52taf2s.apps.googleusercontent.com"

app = FastAPI(title="Stock Discovery Dashboard API (v2.5)")

# Allow CORS for easy development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if os.getenv("TESTING", "false").lower() == "true":
        return await call_next(request)
    path = request.url.path
    
    # Exclude public static files and auth endpoints
    if path in [
        "/login.html", 
        "/api/auth/config", 
        "/api/auth/login", 
        "/style.css", 
        "/app.js", 
        "/favicon.ico"
    ]:
        return await call_next(request)
        
    # Check session cookie
    auth_token = request.cookies.get("auth_token")
    email = verify_session_token(auth_token) if auth_token else None
    
    if email != AUTHORIZED_EMAIL:
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"Access denied. Access is restricted to {AUTHORIZED_EMAIL}."}
            )
        else:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/login.html")
            
    return await call_next(request)

class YoutubeRequest(BaseModel):
    api_key: str
    model: str

class RecommendingRequest(BaseModel):
    api_key: str
    model: str
    market_data: Dict[str, Any]
    news: List[Dict[str, Any]]
    youtube_summaries: List[Dict[str, Any]]

class UploadRequest(BaseModel):
    report_markdown: str

@app.post("/api/pipeline/ingest")
def pipeline_ingest() -> JSONResponse:
    """Step 1: Ingest macro market data (prices, yields, FRED)."""
    logs = ["[SYSTEM] 금융 데이터 수집 및 국면 분석 시작..."]
    try:
        fetcher = AssetDataFetcher()
        market_data_summary = {"macro": {}, "yields": {}, "exchange_rates": {}}
        
        # 1. Fetch yields
        logs.append("[SYSTEM] 미국 10년 국채 금리 수집 중...")
        try:
            df = fetcher.fetch_bond_yield("^TNX", period="5d")
            if not df.empty:
                val = float(df["Yield"].iloc[-1])
                date = df.index[-1].strftime("%Y-%m-%d")
                market_data_summary["yields"]["US10Y"] = {"Yield": val, "Date": date}
                logs.append(f"[SUCCESS] 미국 10년 국채 금리: {val:.2f}% (기준일: {date})")
        except Exception as e:
            logs.append(f"[WARNING] 국채 금리 수집 실패: {str(e)}")
            
        # 2. Fetch exchange rate
        logs.append("[SYSTEM] 원/달러 환율 수집 중...")
        try:
            df = fetcher.fetch_historical_prices("USDKRW=X", period="5d")
            if not df.empty:
                val = float(df["Close"].iloc[-1])
                market_data_summary["exchange_rates"]["USD_KRW"] = {"Close": val}
                logs.append(f"[SUCCESS] 원/달러 환율: {val:.2f}")
        except Exception as e:
            logs.append(f"[WARNING] 환율 수집 실패: {str(e)}")
            
        # 3. Fetch FRED indicators (CPI, FED Rate)
        three_years_ago = get_date_n_days_ago(365 * 3)
        logs.append("[SYSTEM] FRED 매크로 지표(CPI, 기준금리 등) 조회 중...")
        for key, indicator_id in AppConfig.FRED_INDICATORS.items():
            try:
                df = fetcher.fetch_fred_indicator(indicator_id, start_date=three_years_ago)
                if not df.empty:
                    val = float(df["Value"].iloc[-1])
                    date = df.index[-1].strftime("%Y-%m-%d")
                    market_data_summary["macro"][key] = {"Value": val, "Date": date}
                    logs.append(f"[SUCCESS] FRED {key}: {val:.2f} (기준일: {date})")
            except Exception as e:
                logs.append(f"[WARNING] FRED {key} 수집 실패: {str(e)}")
                
        logs.append("[SYSTEM] 1단계: 금융 데이터 수집 완료.")
        return JSONResponse(content={"market_data": market_data_summary, "logs": logs})
    except Exception as e:
        logger.error(f"Ingest step failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "logs": logs + [f"[ERROR] 1단계 실패: {str(e)}"]})

@app.post("/api/pipeline/news")
def pipeline_news() -> JSONResponse:
    """Step 2: Ingest top financial news."""
    logs = ["[SYSTEM] 마켓 주요 뉴스 분석 시작..."]
    try:
        news_fetcher = NewsFetcher()
        news_queries = ["S&P 500", "KOSPI", "US Federal Reserve interest rates", "inflation CPI", "US Treasury bond yields"]
        all_news = []
        for query in news_queries:
            try:
                items = news_fetcher.fetch_query_news(query, limit=3)
                all_news.extend(items)
            except Exception as e:
                logger.warning(f"Could not fetch news for query '{query}': {str(e)}")
        
        seen_titles = set()
        unique_news = []
        for item in all_news:
            title_lower = item["title"].lower()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique_news.append(item)
                
        logs.append(f"[SUCCESS] 총 {len(unique_news)}건의 유니크한 뉴스 헤드라인 수집 완료.")
        logs.append("[SYSTEM] 2단계: 마켓 뉴스 분석 완료.")
        return JSONResponse(content={"news": unique_news, "logs": logs})
    except Exception as e:
        logger.error(f"News step failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "logs": logs + [f"[ERROR] 2단계 실패: {str(e)}"]})

@app.post("/api/pipeline/youtube")
def pipeline_youtube(req: YoutubeRequest) -> JSONResponse:
    """Step 3: Fetch and summarize YouTube videos using provided API Key and Model."""
    logs = ["[SYSTEM] 유튜브 전문가 요약 및 시장 뷰 취합 시작..."]
    try:
        yt_summarizer = YouTubeSummarizer(req.api_key, AppConfig.CHANNEL_ID_MAP, model_name=req.model)
        videos_to_batch = []
        
        for name, handle in AppConfig.YOUTUBE_CHANNELS.items():
            try:
                logs.append(f"[SYSTEM] {handle} 채널 동영상 리스트 로드 중...")
                channel_id = yt_summarizer.resolve_handle_to_id(handle)
                videos = yt_summarizer.fetch_channel_videos_last_48h(channel_id)
                if videos:
                    videos = videos[:1] # Limit to 1 per channel
                for video in videos:
                    video_id = video["video_id"]
                    title = video["title"]
                    try:
                        content = yt_summarizer.get_transcript(video_id)
                    except Exception:
                        content = video.get("description", "")
                    if not content.strip():
                        content = f"Video Title: {title}."
                    
                    videos_to_batch.append({
                        "video_id": video_id, "title": title, "channel_handle": handle,
                        "published_at": video["published_at"], "link": video["link"], "content": content
                    })
            except Exception as e:
                logs.append(f"[WARNING] {handle} 채널 로드 실패: {str(e)}")
                
        youtube_summaries = []
        if videos_to_batch:
            logs.append(f"[SYSTEM] 총 {len(videos_to_batch)}개의 신규 영상을 하나의 배치로 요약 요청 중 (13초 지연 대기)...")
            youtube_summaries = yt_summarizer.summarize_videos_batched(videos_to_batch)
            logs.append("[SUCCESS] 유튜브 전문가 의견 요약 완료.")
        else:
            logs.append("[WARNING] 최근 48시간 내에 업로드된 새로운 영상이 없습니다.")
            
        logs.append("[SYSTEM] 3단계: 유튜브 전문가 요약 완료.")
        return JSONResponse(content={"youtube_summaries": youtube_summaries, "logs": logs})
    except Exception as e:
        logger.error(f"YouTube step failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "logs": logs + [f"[ERROR] 3단계 실패: {str(e)}"]})

@app.post("/api/pipeline/recommending")
def pipeline_recommending(req: RecommendingRequest) -> JSONResponse:
    """Step 4: Compile Recommendation Report using provided API Key and Model."""
    logs = ["[SYSTEM] AI 기반 최종 추천 투자 보고서 합성 시작..."]
    try:
        recommender = RecommendationEngine(req.api_key, model_name=req.model)
        report_markdown = recommender.generate_recommendation_report(
            market=req.market_data,
            news=req.news,
            youtube=req.youtube_summaries
        )
        logs.append("[SUCCESS] 추천 보고서 합성 완료.")
        logs.append("[SYSTEM] 4단계: AI 추천 보고서 생성 완료.")
        return JSONResponse(content={"report_markdown": report_markdown, "logs": logs})
    except Exception as e:
        logger.error(f"Recommending step failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "logs": logs + [f"[ERROR] 4단계 실패: {str(e)}"]})

@app.post("/api/pipeline/upload")
def pipeline_upload(req: UploadRequest) -> JSONResponse:
    """Step 5: Save report locally and upload to Google Drive if configured."""
    logs = ["[SYSTEM] 생성된 보고서 구글 드라이브 및 로컬 아카이빙 시작..."]
    gdoc_link = ""
    timestamp = datetime.now().strftime("%Y-%m-%d")
    local_report_filename = f"reports/{timestamp}_report.md"
    
    # 1. Save locally (attempt, ignore if read-only filesystem)
    try:
        os.makedirs("reports", exist_ok=True)
        with open(local_report_filename, "w", encoding="utf-8") as f:
            f.write(req.report_markdown)
        logs.append(f"[SUCCESS] 로컬 아카이브 저장 성공: reports/{timestamp}_report.md")
    except Exception as e:
        logs.append(f"[WARNING] 로컬 파일 쓰기 실패 (Vercel 환경 등): {str(e)}")
        
    # 2. Upload to Google Drive (if credentials are set and file exists)
    if AppConfig.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(AppConfig.GOOGLE_APPLICATION_CREDENTIALS):
        try:
            # Write to a temp file in /tmp or workspace if local write failed
            temp_path = local_report_filename
            if not os.path.exists(temp_path):
                # Vercel write fallback to /tmp
                temp_path = f"/tmp/{timestamp}_report.md"
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(req.report_markdown)
                    
            uploader = GoogleDriveUploader(
                credentials_path=AppConfig.GOOGLE_APPLICATION_CREDENTIALS,
                token_json_str=AppConfig.GOOGLE_DRIVE_TOKEN_JSON
            )
            uploader.authenticate()
            gdoc_link = uploader.upload_markdown_file(
                local_path=temp_path,
                filename=f"{timestamp}_Investment_Report",
                target_folder_name="Stock_Reports",
                folder_id=AppConfig.GOOGLE_DRIVE_FOLDER_ID
            )
            logs.append(f"[SUCCESS] 구글 드라이브 업로드 완료: {gdoc_link}")
        except Exception as e:
            logs.append(f"[WARNING] 구글 드라이브 업로드 실패: {str(e)}")
    else:
        logs.append("[INFO] 구글 드라이브 크레덴셜 설정이 확인되지 않아 업로드를 생략합니다.")
        
    logs.append("[SYSTEM] 5단계: 아카이빙 및 업로드 완료.")
    return JSONResponse(content={"gdoc_link": gdoc_link, "logs": logs})

# Global lock to ensure only one pipeline thread runs at a time
pipeline_lock = threading.Lock()

def run_pipeline_worker() -> None:
    """Background worker executing the stock discovery and rebalancing pipeline."""
    with pipeline_lock:
        try:
            logger.info("Background pipeline execution started.")
            tracker.reset()
            
            # Load selected model from portfolio database
            pm = PortfolioManager(AppConfig.PORTFOLIO_FILE_PATH)
            try:
                portfolio_raw = pm.load_portfolio()
                selected_model = portfolio_raw.get("gemini_model", "gemini-3.5-flash")
            except Exception:
                selected_model = "gemini-3.5-flash"
            logger.info(f"Using Gemini AI Model: {selected_model}")
            
            # Step 1: Initialize watchlists
            tracker.update("ingesting", 5, "Preparing watchlists and target asset lists...")
            us_watchlist = os.getenv("US_WATCHLIST")
            kr_watchlist = os.getenv("KR_WATCHLIST")
            watchlist_us = [t.strip() for t in us_watchlist.split(",")] if us_watchlist else AppConfig.US_WATCHLIST
            watchlist_kr = [t.strip() for t in kr_watchlist.split(",")] if kr_watchlist else AppConfig.KR_WATCHLIST
            full_equity_watchlist = watchlist_us + watchlist_kr
            
            # Step 2: Fetch prices, yields, FRED
            tracker.update("ingesting", 15, "Fetching live market prices, treasury yields, and FRED indicators...")
            fetcher = AssetDataFetcher()
            market_data: Dict[str, Any] = {
                "prices": {}, "yields": {}, "macro": {}, "exchange_rates": {}
            }
            
            for ticker in full_equity_watchlist:
                try:
                    df = fetcher.fetch_historical_prices(ticker, period="1y", interval="1d")
                    market_data["prices"][ticker] = df
                except Exception as e:
                    logger.warning(f"Could not ingest price history for {ticker}: {str(e)}")

            for key, ticker in AppConfig.MACRO_TICKERS.items():
                if key in ["US10Y", "KR10YT=RR"] or "10Y" in key:
                    try:
                        df = fetcher.fetch_bond_yield(ticker, period="1y")
                        market_data["yields"][key] = df
                    except Exception as e:
                        logger.warning(f"Could not ingest yield for {key} ({ticker}): {str(e)}")
                elif key == "USD_KRW" or ticker == "USDKRW=X":
                    try:
                        df = fetcher.fetch_historical_prices(ticker, period="1y")
                        market_data["exchange_rates"]["USD_KRW"] = df
                    except Exception as e:
                        logger.warning(f"Could not fetch exchange rate {ticker}: {str(e)}")
                else:
                    try:
                        df = fetcher.fetch_historical_prices(ticker, period="1y")
                        market_data["prices"][key] = df
                    except Exception as e:
                        logger.warning(f"Could not fetch macro asset price for {key} ({ticker}): {str(e)}")

            three_years_ago = get_date_n_days_ago(365 * 3)
            for key, indicator_id in AppConfig.FRED_INDICATORS.items():
                try:
                    df = fetcher.fetch_fred_indicator(indicator_id, start_date=three_years_ago)
                    market_data["macro"][key] = df
                except Exception as e:
                    logger.warning(f"Could not fetch FRED indicator {key} ({indicator_id}): {str(e)}")

            # Step 3: Fetch News
            tracker.update("news", 40, "Retrieving recent market headlines via News RSS...")
            news_fetcher = NewsFetcher()
            news_queries = ["S&P 500", "KOSPI", "US Federal Reserve interest rates", "inflation CPI", "US Treasury bond yields"]
            all_news = []
            for query in news_queries:
                try:
                    items = news_fetcher.fetch_query_news(query, limit=4)
                    all_news.extend(items)
                except Exception as e:
                    logger.warning(f"Could not fetch news for query '{query}': {str(e)}")
            
            seen_titles = set()
            unique_news = []
            for item in all_news:
                title_lower = item["title"].lower()
                if title_lower not in seen_titles:
                    seen_titles.add(title_lower)
                    unique_news.append(item)

            # Step 4: Summarize YouTube Transcripts
            tracker.update("youtube", 55, "Summarizing latest financial YouTube expert videos...")
            yt_summarizer = YouTubeSummarizer(AppConfig.GEMINI_API_KEY, AppConfig.CHANNEL_ID_MAP, model_name=selected_model)
            youtube_summaries = []
            videos_to_batch = []
            
            for name, handle in AppConfig.YOUTUBE_CHANNELS.items():
                try:
                    channel_id = yt_summarizer.resolve_handle_to_id(handle)
                    videos = yt_summarizer.fetch_channel_videos_last_48h(channel_id)
                    # Limit to at most 1 video per channel to conserve API quota
                    if videos:
                        videos = videos[:1]
                    for video in videos:
                        video_id = video["video_id"]
                        title = video["title"]
                        try:
                            content = yt_summarizer.get_transcript(video_id)
                        except Exception:
                            content = video.get("description", "")
                        if not content.strip():
                            content = f"Video Title: {title}. No description or transcript was available."
                        
                        videos_to_batch.append({
                            "video_id": video_id, "title": title, "channel_handle": handle,
                            "published_at": video["published_at"], "link": video["link"], "content": content
                        })
                except Exception as e:
                    logger.warning(f"Could not process YouTube channel {handle}: {str(e)}")

            if videos_to_batch:
                youtube_summaries = yt_summarizer.summarize_videos_batched(videos_to_batch)

            # Step 7: Generate Report
            tracker.update("recommending", 92, "Compiling daily recommendation report via Gemini AI...")
            recommender = RecommendationEngine(AppConfig.GEMINI_API_KEY, model_name=selected_model)
            report_markdown = recommender.generate_recommendation_report(
                market=market_data, news=unique_news, youtube=youtube_summaries
            )

            # Step 8: Save Report Locally
            os.makedirs("reports", exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d")
            local_report_filename = f"reports/{timestamp}_report.md"
            with open(local_report_filename, "w", encoding="utf-8") as f:
                f.write(report_markdown)

            # Step 9: Upload to Google Drive (if credentials exist)
            if AppConfig.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(AppConfig.GOOGLE_APPLICATION_CREDENTIALS):
                tracker.update("uploading", 97, "Uploading generated report to Google Drive...")
                uploader = GoogleDriveUploader(
                    credentials_path=AppConfig.GOOGLE_APPLICATION_CREDENTIALS,
                    token_json_str=AppConfig.GOOGLE_DRIVE_TOKEN_JSON
                )
                uploader.authenticate()
                gdoc_link = uploader.upload_markdown_file(
                    local_path=local_report_filename,
                    filename=f"{timestamp}_Investment_Report",
                    target_folder_name="Stock_Reports",
                    folder_id=AppConfig.GOOGLE_DRIVE_FOLDER_ID
                )
                logger.info(f"Report uploaded successfully to Google Drive: {gdoc_link}")
                tracker.update("done", 100, f"Pipeline completed successfully. Google Drive URL: {gdoc_link}")
            else:
                logger.warning("Google Drive credentials not found or unconfigured. Skipping upload.")
                tracker.update("done", 100, "Pipeline completed successfully. (Report archived locally only)")

        except Exception as e:
            logger.error(f"Pipeline background execution failed: {str(e)}")
            tracker.update("failed", 100, f"Execution failed: {str(e)}", error=str(e))


# ==============================================================================
# Static Web Routing
# ==============================================================================

@app.get("/")
def get_dashboard() -> FileResponse:
    """Serves the main dashboard user interface."""
    return FileResponse("app/static/index.html")

@app.get("/login.html")
def get_login() -> FileResponse:
    """Serves the Google sign-in login page."""
    return FileResponse("app/static/login.html")

@app.get("/style.css")
def get_style() -> FileResponse:
    return FileResponse("app/static/style.css")

@app.get("/app.js")
def get_script() -> FileResponse:
    return FileResponse("app/static/app.js")

@app.get("/screener.html")
def get_screener() -> FileResponse:
    """Serves the Stock Screener UI page."""
    return FileResponse("app/static/screener.html")


# ==============================================================================
# API Endpoints
# ==============================================================================

@app.get("/api/status")
def get_status() -> JSONResponse:
    """Returns the in-memory progress status and logs of the running pipeline."""
    return JSONResponse(content=tracker.get_status())

@app.post("/api/run")
def trigger_run() -> JSONResponse:
    """Spawns a background thread to trigger the pipeline on-demand."""
    if tracker.status not in ["idle", "done", "failed"]:
        raise HTTPException(status_code=400, detail="Pipeline is already executing.")
        
    thread = threading.Thread(target=run_pipeline_worker)
    thread.daemon = True
    thread.start()
    
    return JSONResponse(content={"message": "Pipeline run triggered successfully."})

# ==============================
# Stock Screener API Endpoints
# ==============================

@app.post("/api/screener/start")
def screener_start(req: dict) -> JSONResponse:
    """Trigger screener scan for selected market.
    Expected JSON body: {"market": "sp500"}
    """
    market = req.get("market", "sp500")
    if not market:
        raise HTTPException(status_code=400, detail="Market parameter required.")
    manager = ScreenerManager()
    started = manager.start_scan(market)
    if not started:
        return JSONResponse(status_code=409, content={"detail": "Screener already running."})
    return JSONResponse(content={"message": "Screener started", "market": market})

@app.get("/api/screener/status")
def screener_status() -> JSONResponse:
    """Return current screener state including progress, results, and logs."""
    manager = ScreenerManager()
    return JSONResponse(content=manager.get_status())

@app.post("/api/screener/stop")
def screener_stop() -> JSONResponse:
    """Request termination of an ongoing screener scan."""
    manager = ScreenerManager()
    stopped = manager.stop_scan()
    if not stopped:
        return JSONResponse(status_code=400, content={"detail": "Screener not running."})
    return JSONResponse(content={"message": "Screener stop requested"})

@app.get("/api/screener/history/{ticker}")
def get_screener_history(ticker: str) -> JSONResponse:
    """Return recent price and volume arrays for the given ticker.
    The data is used by the frontend Trend button to render a sparkline.
    """
    try:
        fetcher = AssetDataFetcher()
        df = fetcher.fetch_historical_prices(ticker, period="1mo", interval="1d")
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found for ticker")
        
        recent = df.tail(20)
        prices = recent["Close"].astype(float).tolist()
        volumes = recent["Volume"].astype(float).tolist()
        return JSONResponse(content={"prices": prices, "volumes": volumes})
    except Exception as e:
        logger.error(f"Failed to fetch history for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to retrieve ticker history")


# ==============================
# Ticker List Management API Endpoints
# ==============================

@app.get("/api/tickers/{market}")
def get_tickers(market: str) -> JSONResponse:
    """Returns the cached ticker list for the given market."""
    if market not in ["sp500", "kospi200", "kosdaq"]:
        raise HTTPException(status_code=400, detail="Invalid market. Allowed values: sp500, kospi200, kosdaq")
    
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(root_dir, "data", f"tickers_{market}.json")
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tickers = json.load(f)
            return JSONResponse(content={"market": market, "tickers": tickers})
        except Exception as e:
            logger.error(f"Failed to read ticker cache file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to read ticker cache: {str(e)}")
    
    # 파일이 없는 경우, 최초 로드를 수행하여 파일을 자동 생성
    try:
        manager = ScreenerManager()
        tickers = manager._load_tickers(market)
        return JSONResponse(content={"market": market, "tickers": tickers})
    except Exception as e:
        logger.error(f"Failed to initialize ticker list for {market}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize ticker list: {str(e)}")

@app.put("/api/tickers/{market}")
def update_tickers(market: str, tickers: List[Dict[str, str]] = Body(...)) -> JSONResponse:
    """Overwrites the cached ticker list with user provided values."""
    if market not in ["sp500", "kospi200", "kosdaq"]:
        raise HTTPException(status_code=400, detail="Invalid market. Allowed values: sp500, kospi200, kosdaq")
    
    if not isinstance(tickers, list):
        raise HTTPException(status_code=400, detail="Tickers must be a list of strings.")
    
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root_dir, "data")
    file_path = os.path.join(data_dir, f"tickers_{market}.json")
    
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(tickers, f, ensure_ascii=False, indent=4)
        logger.info(f"Ticker list for {market} manually updated via API.")
        return JSONResponse(content={"message": f"Ticker list for {market} updated successfully.", "count": len(tickers)})
    except Exception as e:
        logger.error(f"Failed to update ticker cache file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save ticker cache: {str(e)}")

@app.post("/api/tickers/{market}/refresh")
def refresh_tickers(market: str) -> JSONResponse:
    """Forces refreshing the ticker list from source (Wikipedia/FDR) and saves it."""
    if market not in ["sp500", "kospi200", "kosdaq"]:
        raise HTTPException(status_code=400, detail="Invalid market. Allowed values: sp500, kospi200, kosdaq")
        
    try:
        manager = ScreenerManager()
        # force_refresh=True 로 호출
        tickers = manager._load_tickers(market, force_refresh=True)
        return JSONResponse(content={"message": f"Ticker list for {market} refreshed successfully.", "count": len(tickers), "tickers": tickers})
    except Exception as e:
        logger.error(f"Failed to refresh ticker list for {market}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh ticker list: {str(e)}")


@app.get("/api/portfolio")
def get_portfolio() -> JSONResponse:
    """Reads and returns the portfolio holdings database."""
    pm = PortfolioManager(AppConfig.PORTFOLIO_FILE_PATH)
    try:
        data = pm.load_portfolio()
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load portfolio: {str(e)}")

@app.post("/api/portfolio")
def update_portfolio(data: Dict[str, Any] = Body(...)) -> JSONResponse:
    """Validates and updates the portfolio database."""
    pm = PortfolioManager(AppConfig.PORTFOLIO_FILE_PATH)
    try:
        # Elementary target allocation weight check
        target = data.get("target_allocation", {})
        total_weight = sum(target.values())
        if abs(total_weight - 1.0) > 0.001:
            raise HTTPException(status_code=400, detail="Target allocation weights must sum exactly to 1.0.")
            
        pm.save_portfolio(data)
        logger.info("Portfolio database updated via Web UI.")
        return JSONResponse(content={"message": "Portfolio database updated successfully."})
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update portfolio: {str(e)}")

@app.get("/api/settings/db")
def get_db_settings() -> JSONResponse:
    """Returns the current database connection settings (excluding password)."""
    return JSONResponse(content={
        "db_type": os.getenv("DB_TYPE", ""),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": os.getenv("DB_PORT", "3306"),
        "db_user": os.getenv("DB_USER", ""),
        "db_name": os.getenv("DB_NAME", ""),
        "has_password": bool(os.getenv("DB_PASSWORD"))
    })

@app.post("/api/settings/db")
def update_db_settings(data: Dict[str, Any] = Body(...)) -> JSONResponse:
    """Updates the DB configuration in memory, writes to .env, and reinitializes the connection."""
    db_type = data.get("db_type", "").strip()
    db_host = data.get("db_host", "").strip()
    db_port = data.get("db_port", "").strip()
    db_user = data.get("db_user", "").strip()
    db_password = data.get("db_password", "").strip()
    db_name = data.get("db_name", "").strip()

    # 1. Update os.environ
    os.environ["DB_TYPE"] = db_type
    os.environ["DB_HOST"] = db_host
    os.environ["DB_PORT"] = db_port
    os.environ["DB_USER"] = db_user
    if db_password or "db_password" in data:
        os.environ["DB_PASSWORD"] = db_password
    os.environ["DB_NAME"] = db_name

    # 2. Write to .env file to persist changes
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            pass

    # Create map of database keys
    db_keys = ["DB_TYPE", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    
    # Filter out existing database config lines
    new_lines = []
    for line in lines:
        is_db_line = False
        for key in db_keys:
            if line.startswith(f"{key}="):
                is_db_line = True
                break
        if not is_db_line:
            new_lines.append(line)
            
    # Append the new config parameters
    new_lines.append("\n# --- DATABASE CONFIGURATION (UPDATED VIA WEB UI) ---\n")
    new_lines.append(f"DB_TYPE={db_type}\n")
    new_lines.append(f"DB_HOST={db_host}\n")
    new_lines.append(f"DB_PORT={db_port}\n")
    new_lines.append(f"DB_USER={db_user}\n")
    if db_password or "db_password" in data:
        new_lines.append(f"DB_PASSWORD={db_password}\n")
    else:
        # Keep old password from env if not provided
        old_pw = os.getenv("DB_PASSWORD", "")
        new_lines.append(f"DB_PASSWORD={old_pw}\n")
    new_lines.append(f"DB_NAME={db_name}\n")

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning(f"Could not write to .env (normal on serverless read-only filesystem): {str(e)}")

    # 3. Reinitialize the DB connection
    from app.database import init_db
    success = init_db()

    if not db_type:
        return JSONResponse(content={"message": "데이터베이스 연동이 비활성화되었습니다.", "connected": False})
        
    if success:
        return JSONResponse(content={"message": "데이터베이스 설정 저장 및 연결에 성공하였습니다!", "connected": True})
    else:
        return JSONResponse(status_code=400, content={"message": "데이터베이스 연결에 실패하였습니다. 설정을 확인해 주십시오.", "connected": False})

@app.get("/api/reports")
def get_reports_list() -> JSONResponse:
    """Returns a list of reports from Google Drive (synced) or local folder as fallback."""
    # 1. Try to list files from Google Drive
    token_json = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    folder_id = AppConfig.GOOGLE_DRIVE_FOLDER_ID
    if token_json and folder_id:
        try:
            uploader = GoogleDriveUploader(token_json_str=token_json)
            uploader.authenticate()
            files = uploader.list_files_in_folder(folder_id)
            files.sort(reverse=True)
            return JSONResponse(content=files)
        except Exception as e:
            logger.warning(f"Failed to fetch reports list from Google Drive: {str(e)}. Falling back to local files.")

    # 2. Fallback to local files
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        return JSONResponse(content=[])
        
    files = [f for f in os.listdir(reports_dir) if f.endswith(".md")]
    files.sort(reverse=True)
    return JSONResponse(content=files)

@app.get("/api/reports/{filename}")
def get_report_content(filename: str) -> JSONResponse:
    """Serves the contents of a specific archived report from Google Drive or local filesystem."""
    if ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    # 1. Try to read from Google Drive
    token_json = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    folder_id = AppConfig.GOOGLE_DRIVE_FOLDER_ID
    if token_json and folder_id:
        try:
            uploader = GoogleDriveUploader(token_json_str=token_json)
            uploader.authenticate()
            content = uploader.download_file_by_name(filename, folder_id)
            if content is not None:
                return JSONResponse(content={"filename": filename, "content": content})
        except Exception as e:
            logger.warning(f"Failed to read report '{filename}' from Google Drive: {str(e)}. Falling back to local file.")

    # 2. Fallback to local file
    path = os.path.join("reports", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report file not found.")
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse(content={"filename": filename, "content": content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read local report content: {str(e)}")

@app.get("/api/portfolio/gspread")
def get_gspread_portfolio() -> JSONResponse:
    """Fetches real-time portfolio holdings from Google Spreadsheet."""
    try:
        holdings = fetch_portfolio_holdings()
        return JSONResponse(content=holdings)
    except Exception as e:
        logger.error(f"Endpoint /api/portfolio/gspread failed: {str(e)}")
        # Raise HTTP 500 or return empty list with error detail
        return JSONResponse(status_code=500, content={"error": str(e), "message": "Failed to fetch spreadsheet holdings."})

def _get_latest_recommendation_report() -> Optional[Dict[str, str]]:
    # 1. Try to list files from Google Drive
    token_json = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    folder_id = AppConfig.GOOGLE_DRIVE_FOLDER_ID
    if token_json and folder_id:
        try:
            uploader = GoogleDriveUploader(token_json_str=token_json)
            uploader.authenticate()
            files = uploader.list_files_in_folder(folder_id)
            report_files = [f for f in files if "rebalance" not in f.lower() and "strategy" not in f.lower()]
            if report_files:
                report_files.sort(reverse=True)
                latest_filename = report_files[0]
                content = uploader.download_file_by_name(latest_filename, folder_id)
                if content:
                    return {"filename": latest_filename, "content": content}
        except Exception as e:
            logger.warning(f"Failed to fetch latest report from Google Drive: {str(e)}")
    
    # 2. Try local files
    reports_dir = "reports"
    if os.path.exists(reports_dir):
        files = [f for f in os.listdir(reports_dir) if f.endswith(".md") and "rebalance" not in f.lower() and "strategy" not in f.lower()]
        if files:
            files.sort(reverse=True)
            latest_filename = files[0]
            try:
                with open(os.path.join(reports_dir, latest_filename), "r", encoding="utf-8") as f:
                    content = f.read()
                return {"filename": latest_filename, "content": content}
            except Exception as e:
                logger.warning(f"Failed to read local report: {str(e)}")
    return None

def _get_latest_rebalance_strategy() -> Optional[Dict[str, str]]:
    # 1. Try to list files from Google Drive
    token_json = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    folder_id = AppConfig.GOOGLE_DRIVE_FOLDER_ID
    if token_json and folder_id:
        try:
            uploader = GoogleDriveUploader(token_json_str=token_json)
            uploader.authenticate()
            files = uploader.list_files_in_folder(folder_id)
            rebalance_files = [f for f in files if "rebalance" in f.lower() or "strategy" in f.lower()]
            if rebalance_files:
                rebalance_files.sort(reverse=True)
                latest_filename = rebalance_files[0]
                content = uploader.download_file_by_name(latest_filename, folder_id)
                if content:
                    return {"filename": latest_filename, "content": content}
        except Exception as e:
            logger.warning(f"Failed to fetch latest rebalance strategy from Google Drive: {str(e)}")
    
    # 2. Try local files
    reports_dir = "reports"
    if os.path.exists(reports_dir):
        files = [f for f in os.listdir(reports_dir) if f.endswith(".md") and ("rebalance" in f.lower() or "strategy" in f.lower())]
        if files:
            files.sort(reverse=True)
            latest_filename = files[0]
            try:
                with open(os.path.join(reports_dir, latest_filename), "r", encoding="utf-8") as f:
                    content = f.read()
                return {"filename": latest_filename, "content": content}
            except Exception as e:
                logger.warning(f"Failed to read local rebalance strategy: {str(e)}")
    return None

class RebalanceRequest(BaseModel):
    api_key: str
    model: str

@app.get("/api/portfolio/rebalance")
def get_rebalance_strategy() -> JSONResponse:
    """Retrieves the latest generated portfolio rebalancing strategy."""
    strategy = _get_latest_rebalance_strategy()
    if strategy:
        return JSONResponse(content=strategy)
    return JSONResponse(content={"filename": "", "content": "아직 생성된 리밸런싱 전략이 없습니다. 'AI 리밸런싱 전략 생성' 버튼을 클릭하십시오."})

@app.post("/api/portfolio/rebalance")
def generate_rebalance_strategy(req: RebalanceRequest) -> JSONResponse:
    """Generates a customized portfolio rebalancing strategy using Gemini AI."""
    if not req.api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is required.")
        
    try:
        # 1. Fetch real-time holdings
        holdings = fetch_portfolio_holdings()
        if not holdings:
            return JSONResponse(status_code=400, content={"error": "Holdings are empty. Cannot rebalance empty portfolio."})
            
        # 2. Get latest recommendation report
        latest_report = _get_latest_recommendation_report()
        if not latest_report:
            return JSONResponse(status_code=400, content={"error": "Latest recommendation report not found. Please run automated analysis first."})
            
        # 2.5 Compute Quant Scores for holdings + watchlists
        logger.info("Computing Quant Entry & Evaluation scores for portfolio and watchlist...")
        from app.scoring import QuantScorer
        us_watchlist = os.getenv("US_WATCHLIST")
        kr_watchlist = os.getenv("KR_WATCHLIST")
        watchlist_us = [t.strip() for t in us_watchlist.split(",")] if us_watchlist else AppConfig.US_WATCHLIST
        watchlist_kr = [t.strip() for t in kr_watchlist.split(",")] if kr_watchlist else AppConfig.KR_WATCHLIST
        
        holding_tickers = [h["ticker"] for h in holdings]
        all_candidate_tickers = list(set(holding_tickers + watchlist_us + watchlist_kr))
        
        scorer = QuantScorer()
        quant_scores = scorer.calculate_scores(all_candidate_tickers)
        
        # Format scores text
        scores_text = ""
        for ticker, score in quant_scores.items():
            fundamentals = score.get("fundamentals", {})
            ma = score.get("moving_averages", {})
            vol = score.get("volume", {})
            
            per_str = f"{fundamentals.get('per'):.2f}" if isinstance(fundamentals.get('per'), (int, float)) else "N/A"
            peg_str = f"{fundamentals.get('peg'):.2f}" if isinstance(fundamentals.get('peg'), (int, float)) else "N/A"
            eps_str = f"{fundamentals.get('eps'):.2f}" if isinstance(fundamentals.get('eps'), (int, float)) else "N/A"
            fwd_eps_str = f"{fundamentals.get('fwd_eps'):.2f}" if isinstance(fundamentals.get('fwd_eps'), (int, float)) else "N/A"
            target_price_str = f"{fundamentals.get('target_price'):.2f}" if isinstance(fundamentals.get('target_price'), (int, float)) else "N/A"
            
            scores_text += (
                f"- **{ticker}** ({score['name']}):\n"
                f"  * **진입 점수 (Entry Score)**: {score['entry_score']}/100\n"
                f"    - 진입 분석 상세: {', '.join(score['entry_details'])}\n"
                f"    - 이평선: 5일선={ma.get('sma_5', 0.0):.2f} | 20일선={ma.get('sma_20', 0.0):.2f} | 200일선={ma.get('sma_200', 0.0):.2f}\n"
                f"    - 거래량: 현재={vol.get('current', 0.0):.0f} | 20일평균={vol.get('avg_20', 0.0):.0f}\n"
                f"  * **평가 점수 (Evaluation Score)**: {score['eval_score']}/100\n"
                f"    - 평가 분석 상세: {', '.join(score['eval_details'])}\n"
                f"    - 지표: PER={per_str} | PEG={peg_str} | EPS={eps_str} | FWD EPS={fwd_eps_str} | 예상 목표가={target_price_str}\n"
            )

        # 3. Call Gemini to generate strategy
        import google.generativeai as genai
        genai.configure(api_key=req.api_key)
        
        # Format holdings for prompt
        holdings_text = ""
        for h in holdings:
            holdings_text += (
                f"- Ticker: {h['ticker']} | Name: {h['name']} | Qty: {h['quantity']} "
                f"| Current Price: {h['current_price']} | Purchase Price: {h['purchase_price']} "
                f"| Total Purchase: {h['total_purchase']} | Total Evaluation: {h['total_evaluation']} "
                f"| Profit/Loss: {h['profit']} | ROI: {h['roi']} | Weight: {h['weight']}\n"
            )
            
        # Compose prompt
        prompt = f"""
You are an Elite Portfolio Strategist and Quant Investment Expert.
Your task is to analyze the investor's current portfolio holdings and compare it with the latest daily investment recommendation report to propose a detailed, customized asset rebalancing strategy.

### USER CURRENT HOLDINGS (Google Spreadsheet):
{holdings_text}

### LATEST DAILY INVESTMENT RECOMMENDATIONS:
{latest_report['content']}

### QUANT ENTRY & EVALUATION SCORES (이평선, 거래량, 밸류에이션, 목표가, CANSLIM 분석 기반):
{scores_text}

---

다음 지침에 맞춰 전문적이고 완성도 높은 한국어 포트폴리오 리밸런싱 전략 보고서(Korean Rebalancing Strategy Report)를 생성해 주세요:
1. **보고서 제목 (Report Title)**: '# 실시간 AI 포트폴리오 리밸런싱 전략 제안'으로 시작해 주세요.
2. **종합 자산 분석 요약 (Summary)**: 현재 포트폴리오의 구조(주식, 환율 노출, 섹터 집중 등)와 최근 마켓 국면을 비교 분석하여 주요 기회 및 위험 요인을 서술해 주세요.
3. **신규 추천 종목 편입 제안 (New Stock Recommendations)**:
   - 최신 투자 추천 보고서에서 매수/롱(Buy/Long)으로 추천하는 종목들 중, 현재 포트폴리오에 **보유하고 있지 않은 신규 추천 종목**이 있다면 반드시 포트폴리오에 새롭게 매수/편입하도록 제안해야 합니다.
   - 기존의 비중이 비대하거나 성과가 좋지 않은 종목, 또는 추천 보고서에서 매도/회피(Sell/Avoid)를 권고하는 종목의 비중을 일부 축소하여 확보한 자금을 이 신규 추천 종목의 매수 자금으로 활용하는 구체적인 자금 배분 전략을 제시해 주세요.
4. **구체적인 리밸런싱 액션 플랜 (Rebalancing Table)**: 사용자가 한눈에 매매 내용을 볼 수 있게 마크다운 테이블 형식으로 작성해 주세요.
   - **열 구성**: | 종목명 (티커) | 현재 비중 | 제안 액션 (매수/매도/유지/신규 매수) | 제안 비중/방향 | 진입 점수 (이평선/거래량) | 평가 점수 (밸류/성장/CANSLIM) | 핵심 근거 |
   - 진입 점수 및 평가 점수 열에는 제공된 ### QUANT ENTRY & EVALUATION SCORES 의 값을 정확하게 표기해 주세요.
   - 신규 편입 종목의 경우 '현재 비중'을 '0.0% (없음)'으로 기재하고 '제안 액션'을 '신규 매수' 또는 '신규 편입'으로 표기해 주세요.
5. **세부 조정 근거 및 추천 사유 (Detailed Rationale)**:
   - 각 종목에 대해 왜 그러한 제안(매수/매도/유지/신규 매수)을 하는지 구체적인 근거를 제시해 주세요.
   - **중요**: 세부 근거 작성 시, 각 종목의 5일, 20일, 200일 이평선 및 거래량 추이(진입 점수 요인)와 PER, PEG, Forward EPS 성장성, 목표가 괴리율(평가 점수 요인) 수치를 구체적으로 언급하며 설명해 주세요.

모든 제안과 분석은 금융 전문가의 어조(Professional Tone)로 격식 있게 작성되어야 합니다.
"""
        
        try:
            model = genai.GenerativeModel(req.model)
        except Exception:
            model = genai.GenerativeModel("gemini-2.5-flash")
            
        # Add a short delay to respect rate limit
        time.sleep(1.0)
        
        response = model.generate_content(prompt)
        strategy_markdown = response.text.strip()
        
        # 4. Save and Upload
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        local_filename = f"reports/{timestamp}_rebalance_strategy.md"
        
        # Save locally
        try:
            os.makedirs("reports", exist_ok=True)
            with open(local_filename, "w", encoding="utf-8") as f:
                f.write(strategy_markdown)
        except Exception as e:
            logger.warning(f"Failed to write rebalance strategy locally: {str(e)}")
            
        # Upload to Google Drive
        gdoc_link = ""
        if AppConfig.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(AppConfig.GOOGLE_APPLICATION_CREDENTIALS):
            try:
                temp_path = local_filename
                if not os.path.exists(temp_path):
                    temp_path = f"/tmp/{timestamp}_rebalance_strategy.md"
                    with open(temp_path, "w", encoding="utf-8") as f:
                        f.write(strategy_markdown)
                        
                uploader = GoogleDriveUploader(
                    credentials_path=AppConfig.GOOGLE_APPLICATION_CREDENTIALS,
                    token_json_str=AppConfig.GOOGLE_DRIVE_TOKEN_JSON
                )
                uploader.authenticate()
                gdoc_link = uploader.upload_markdown_file(
                    local_path=temp_path,
                    filename=f"{timestamp}_Rebalance_Strategy",
                    target_folder_name="Stock_Reports",
                    folder_id=AppConfig.GOOGLE_DRIVE_FOLDER_ID
                )
                logger.info(f"Rebalance strategy uploaded to Google Drive: {gdoc_link}")
            except Exception as e:
                logger.warning(f"Failed to upload rebalance strategy to Google Drive: {str(e)}")
                
        return JSONResponse(content={
            "filename": f"{timestamp}_rebalance_strategy.md",
            "content": strategy_markdown,
            "gdoc_link": gdoc_link
        })
        
    except Exception as e:
        logger.error(f"Generate rebalance strategy failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate rebalance strategy: {str(e)}")


# ==============================================================================
# Authentication API Endpoints
# ==============================================================================

class LoginRequest(BaseModel):
    credential: str

@app.get("/api/auth/config")
def auth_config() -> JSONResponse:
    return JSONResponse(content={"client_id": get_google_client_id()})

@app.post("/api/auth/login")
def auth_login(payload: LoginRequest, request: Request) -> JSONResponse:
    try:
        tokeninfo_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={payload.credential}"
        resp = requests.get(tokeninfo_url, timeout=10)
        
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google credential token.")
            
        token_data = resp.json()
        email = token_data.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not present in Google token.")
            
        if email != AUTHORIZED_EMAIL:
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. Email {email} is not authorized."
            )
            
        session_token = generate_session_token(email)
        
        response = JSONResponse(content={"status": "success", "email": email})
        is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(
            key="auth_token",
            value=session_token,
            httponly=True,
            samesite="none" if is_https else "lax",
            secure=is_https
        )
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Login failed with error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

@app.post("/api/auth/logout")
def auth_logout() -> JSONResponse:
    response = JSONResponse(content={"status": "success", "message": "Logged out successfully."})
    response.delete_cookie("auth_token")
    return response
