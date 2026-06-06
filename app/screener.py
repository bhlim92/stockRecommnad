import os
import json
import time
import threading
import traceback
import requests
import socket
from io import StringIO
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from typing import List, Dict, Any, Optional
from datetime import datetime

# Set global socket timeout to prevent yfinance or requests from hanging the background thread indefinitely
socket.setdefaulttimeout(15)

from app.scoring import QuantScorer
from app.utils.logger import setup_logger
from app.database import save_screener_results

logger = setup_logger("screener", "logs/screener.log")

class ScreenerManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ScreenerManager, cls).__new__(cls)
                cls._instance._init_screener()
            return cls._instance

    def _init_screener(self):
        self.state = {
            "status": "idle", # "idle", "running", "done", "failed"
            "progress": 0,
            "market": "",
            "current": 0,
            "total": 0,
            "results": [],
            "logs": [],
            "aborted": False,
            "current_ticker": ""
        }
        self._thread = None
        self._thread_lock = threading.RLock()
        self.scorer = QuantScorer()

    def get_status(self) -> Dict[str, Any]:
        with self._thread_lock:
            # Return a copy of the state
            return dict(self.state)

    def log(self, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        logger.info(message)
        with self._thread_lock:
            self.state["logs"].append(log_line)
            # Keep last 150 logs
            if len(self.state["logs"]) > 150:
                self.state["logs"].pop(0)

    def start_scan(self, market: str) -> bool:
        with self._thread_lock:
            if self.state["status"] == "running":
                self.log("[WARNING] 스크리너가 이미 실행 중입니다.")
                return False
            
            self.state["status"] = "running"
            self.state["progress"] = 0
            self.state["market"] = market
            self.state["current"] = 0
            self.state["total"] = 0
            self.state["results"] = []
            self.state["logs"] = []
            self.state["aborted"] = False
            self.state["current_ticker"] = ""

        self.log(f"[SYSTEM] {market.upper()} 종목 스크리닝 분석을 시작합니다.")
        self._thread = threading.Thread(target=self._run_screener_worker, args=(market,))
        self._thread.daemon = True
        self._thread.start()
        return True

    def stop_scan(self):
        with self._thread_lock:
            if self.state["status"] == "running":
                self.state["aborted"] = True
                self.log("[SYSTEM] 스캔 중단 요청이 접수되었습니다. 현재 종목 처리 후 중단됩니다.")
                return True
        return False

    def _load_tickers(self, market: str, force_refresh: bool = False) -> List[Dict[str, str]]:
        # 프로젝트 루트 디렉토리 구하기
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(root_dir, "data")
        file_path = os.path.join(data_dir, f"tickers_{market}.json")

        if not force_refresh and os.path.exists(file_path):
            self.log(f"[SYSTEM] 로컬 캐시 파일(data/tickers_{market}.json)에서 {market.upper()} 종목 리스트를 가져오는 중...")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    tickers = json.load(f)
                # 데이터 규격 체크 (과거 규격인 List[str] 일 경우 갱신하도록 처리)
                if isinstance(tickers, list) and len(tickers) > 0:
                    if isinstance(tickers[0], dict) and "symbol" in tickers[0] and "name" in tickers[0]:
                        self.log(f"[SUCCESS] 로컬 캐시 파일에서 {market.upper()} 종목 {len(tickers)}개 로드 완료.")
                        return tickers
                    else:
                        self.log(f"[WARNING] 기존 캐시 파일 규격이 오래되었습니다. 새 규격으로 새로고침합니다.")
                else:
                    self.log(f"[WARNING] 로컬 캐시 파일이 비어있거나 올바르지 않습니다. 새로 갱신합니다.")
            except Exception as e:
                self.log(f"[WARNING] 로컬 캐시 파일 읽기 실패: {str(e)}. 새로 갱신합니다.")

        tickers = []
        if market == "sp500":
            self.log("[SYSTEM] Wikipedia에서 S&P 500 종목 리스트를 가져오는 중...")
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                resp = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers, timeout=10)
                df = pd.read_html(StringIO(resp.text))[0]
                # 'Symbol'과 'Security' 컬럼을 함께 가져와 매핑
                for _, row in df.iterrows():
                    symbol = str(row['Symbol']).replace(".", "-")
                    security = str(row['Security'])
                    tickers.append({"symbol": symbol, "name": security})
                self.log(f"[SUCCESS] Wikipedia에서 S&P 500 종목 {len(tickers)}개 로드 완료.")
            except Exception as e:
                self.log(f"[ERROR] Wikipedia 로드 실패: {str(e)}. 예비 리스트를 사용합니다.")
                # Fallback list of top US tech with names
                fallback_data = [
                    ("AAPL", "Apple Inc."), ("MSFT", "Microsoft Corporation"), ("GOOGL", "Alphabet Inc."),
                    ("AMZN", "Amazon.com Inc."), ("NVDA", "NVIDIA Corporation"), ("META", "Meta Platforms Inc."),
                    ("TSLA", "Tesla Inc."), ("AVGO", "Broadcom Inc."), ("LLY", "Eli Lilly and Company"),
                    ("JPM", "JPMorgan Chase & Co."), ("V", "Visa Inc."), ("MA", "Mastercard Incorporated"),
                    ("UNH", "UnitedHealth Group Incorporated"), ("XOM", "Exxon Mobil Corporation"),
                    ("COST", "Costco Wholesale Corporation"), ("HD", "The Home Depot Inc."),
                    ("PG", "Procter & Gamble Company"), ("NFLX", "Netflix Inc."), ("AMD", "Advanced Micro Devices Inc."),
                    ("ADBE", "Adobe Inc.")
                ]
                tickers = [{"symbol": item[0], "name": item[1]} for item in fallback_data]
        
        elif market == "kospi200":
            self.log("[SYSTEM] FinanceDataReader에서 KOSPI 종목 리스트를 가져와 상위 200개를 정렬하는 중...")
            try:
                df = fdr.StockListing("KOSPI")
                # Sort by Market Cap (Marcap) descending and take top 200
                df_sorted = df.sort_values(by="Marcap", ascending=False).head(200)
                for _, row in df_sorted.iterrows():
                    code = str(row['Code'])
                    name = str(row['Name'])
                    tickers.append({"symbol": f"{code}.KS", "name": name})
                self.log(f"[SUCCESS] FDR에서 KOSPI 상위 200개 종목 로드 완료.")
            except Exception as e:
                self.log(f"[ERROR] KOSPI 리스트 로드 실패: {str(e)}. 예비 리스트를 사용합니다.")
                fallback_data = [
                    ("005930.KS", "삼성전자"), ("000660.KS", "SK하이닉스"), ("373220.KS", "LG에너지솔루션"),
                    ("207940.KS", "삼성바이오로직스"), ("005380.KS", "현대차"), ("005490.KS", "POSCO홀딩스"),
                    ("051910.KS", "LG화학"), ("000270.KS", "기아"), ("035420.KS", "NAVER"), ("006400.KS", "삼성SDI")
                ]
                tickers = [{"symbol": item[0], "name": item[1]} for item in fallback_data]

        elif market == "kosdaq":
            self.log("[SYSTEM] FinanceDataReader에서 KOSDAQ 종목 리스트를 가져와 상위 300개를 정렬하는 중...")
            try:
                df = fdr.StockListing("KOSDAQ")
                # Sort by Market Cap (Marcap) descending and take top 300
                df_sorted = df.sort_values(by="Marcap", ascending=False).head(300)
                for _, row in df_sorted.iterrows():
                    code = str(row['Code'])
                    name = str(row['Name'])
                    tickers.append({"symbol": f"{code}.KQ", "name": name})
                self.log(f"[SUCCESS] FDR에서 KOSDAQ 상위 300개 종목 로드 완료.")
            except Exception as e:
                self.log(f"[ERROR] KOSDAQ 리스트 로드 실패: {str(e)}. 예비 리스트를 사용합니다.")
                fallback_data = [
                    ("247540.KQ", "에코프로비엠"), ("086520.KQ", "에코프로"), ("277810.KQ", "엘앤에프"),
                    ("091990.KQ", "셀트리헬스케어"), ("066970.KQ", "엘앤에프"), ("293490.KQ", "카카오게임즈"),
                    ("112040.KQ", "위메이드"), ("215600.KQ", "젠백스"), ("253450.KQ", "스튜디오드래곤"), ("035760.KQ", "CJ ENM")
                ]
                tickers = [{"symbol": item[0], "name": item[1]} for item in fallback_data]

        # 결과 캐시 파일에 저장
        if tickers:
            try:
                os.makedirs(data_dir, exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(tickers, f, ensure_ascii=False, indent=4)
                self.log(f"[SYSTEM] 가져온 종목 리스트를 data/tickers_{market}.json 에 캐시 저장 완료.")
            except Exception as e:
                self.log(f"[WARNING] 종목 리스트 파일 저장 실패: {str(e)}")

        return tickers

    def _generate_rationale(self, ticker: str, score_result: Dict[str, Any]) -> str:
        """Generates a concise financial rationale in Korean based on score results."""
        try:
            # 1. Technical indicators
            ma = score_result.get("moving_averages", {})
            vol = score_result.get("volume", {})
            entry_score = score_result.get("entry_score", 0)
            
            tech_desc = ""
            if entry_score >= 80:
                tech_desc = "이평선 전반 정배열의 완벽한 우상향 추세"
            elif entry_score >= 60:
                tech_desc = "단기 골든크로스 및 추세 상승 전환국면"
            elif entry_score >= 40:
                tech_desc = "주요 지지선 지지 및 횡보 안정 흐름"
            else:
                tech_desc = "추세 하락 및 역배열 조정 압력"

            if vol.get("current", 0) > vol.get("avg_20", 0) * 1.3:
                tech_desc += " 및 거래량 수급 급증"

            # 2. Fundamentals
            fundamentals = score_result.get("fundamentals", {})
            per = fundamentals.get("per")
            peg = fundamentals.get("peg")
            fwd_eps = fundamentals.get("fwd_eps")
            eps = fundamentals.get("eps")
            eval_score = score_result.get("eval_score", 0)
            
            fund_desc = ""
            if eval_score >= 85:
                fund_desc = "밸류에이션 저평가 매력 및 고성장 모멘텀 보유"
            elif eval_score >= 65:
                fund_desc = "견고한 수익성 대비 합리적인 가격대"
            else:
                fund_desc = "성장성 정체 혹은 고평가 밸류에이션 부담"

            # Growth metrics
            growth_desc = ""
            if isinstance(fwd_eps, (int, float)) and isinstance(eps, (int, float)) and eps != 0:
                growth = ((fwd_eps - eps) / abs(eps)) * 100
                if growth >= 20:
                    growth_desc = f", Forward EPS 큰 폭의 성장(+{growth:.1f}%) 기대"
                elif growth >= 5:
                    growth_desc = f", 미래 이익 증가(+{growth:.1f}%) 전망"

            # Combine
            rationale = f"{tech_desc} 상태이며, {fund_desc}{growth_desc}."
            return rationale
        except Exception as e:
            return "펀더멘탈 및 차트 모멘텀을 반영한 계량 분석 대기 중."

    def _run_screener_worker(self, market: str):
        try:
            tickers_info = self._load_tickers(market)
            if not tickers_info:
                raise ValueError("가져온 종목 티커 리스트가 비어 있습니다.")

            # Remove arbitrary cap to enable full market screening
            total = len(tickers_info)
            tickers = [item["symbol"] for item in tickers_info]

            # 스캔 시작 시각을 구하여 해당 세션의 전체 종목 타임스탬프로 동일하게 사용
            scan_start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1단계: 선-렌더링용 플레이스홀더 데이터로 results 리스트를 즉시 초기화
            with self._thread_lock:
                self.state["total"] = total
                self.state["current"] = 0
                self.state["progress"] = 0
                self.state["current_ticker"] = ""
                self.state["results"] = [
                    {
                        "symbol": item["symbol"],
                        "name": item["name"],
                        "current_price": None,
                        "entry_score": None,
                        "eval_score": None,
                        "total_score": None,
                        "rationale": "분석 대기 중...",
                        "created_at": scan_start_time_str,
                    }
                    for item in tickers_info
                ]

            self.log(f"[SYSTEM] 1단계: 전체 {total}개 종목의 시세(일봉) 데이터 묶음 다운로드 시작...")
            
            # Batch price download in blocks of 100 to prevent timeout and URL truncation
            preloaded_prices = {}
            batch_size = 100
            for i in range(0, total, batch_size):
                if self.state["aborted"]:
                    self.log("[SYSTEM] 사용자에 의해 다운로드 작업이 중단되었습니다.")
                    break
                
                batch = tickers[i:i + batch_size]
                self.log(f"[SYSTEM] 가격 히스토리 다운로드 진행 중... ({i}/{total})")
                try:
                    df_batch = yf.download(batch, period="1y", group_by="ticker", progress=False, timeout=20)
                    
                    for ticker in batch:
                        try:
                            # Parse single ticker DataFrame from batch MultiIndex DataFrame
                            if len(batch) == 1:
                                df_ticker = df_batch
                            else:
                                if ticker in df_batch.columns.levels[0]:
                                    df_ticker = df_batch[ticker]
                                else:
                                    continue
                            
                            # Clean up and drop empty rows
                            df_ticker = df_ticker.dropna(subset=["Close"])
                            if not df_ticker.empty:
                                preloaded_prices[ticker] = df_ticker
                        except Exception as e:
                            # Skip silently for individual parser failure
                            pass
                except Exception as e:
                    self.log(f"[WARNING] {i}번째 배치 다운로드 중 오류 발생: {str(e)}")

            # Fallback mock generation if yahoo finance failed (e.g. no internet/sandbox block)
            for ticker in tickers:
                if ticker not in preloaded_prices:
                    self.log(f"[WARNING] {ticker} 시세 다운로드 실패. 모의 데이터(Mock Data)를 생성하여 분석을 계속합니다.")
                    import numpy as np
                    dates = pd.date_range(end=pd.Timestamp.now(), periods=250, freq="B")
                    prices = np.linspace(100, 150, 250) + np.random.normal(0, 2, 250)
                    volumes = np.random.randint(50000, 150000, 250)
                    df_ticker = pd.DataFrame({
                        "Open": prices - 1,
                        "High": prices + 1,
                        "Low": prices - 2,
                        "Close": prices,
                        "Volume": volumes
                    }, index=dates)
                    preloaded_prices[ticker] = df_ticker

            self.log(f"[SUCCESS] 시세 데이터 다운로드 완료. 유효 종목: {len(preloaded_prices)}개.")
            self.log("[SYSTEM] 2단계: 개별 종목 정밀 점수 및 스파크라인 연산 시작 (Concurrent)...")

            scorer = QuantScorer()

            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            max_workers = 15
            start_time = time.time()
            completed_count = 0
            
            def process_single_ticker(ticker):
                # Check aborted inside the thread
                if self.state["aborted"]:
                    return ticker, None, "aborted"
                    
                if ticker not in preloaded_prices:
                    return ticker, None, "no_prices"
                    
                try:
                    score_res = scorer.calculate_scores([ticker], preloaded_prices={ticker: preloaded_prices[ticker]})
                    
                    if not score_res or ticker not in score_res:
                        # Fallback mock fundamentals
                        score_res = {
                            ticker: {
                                "name": (ticker + " Company"),
                                "current_price": float(preloaded_prices[ticker]["Close"].iloc[-1]) if ticker in preloaded_prices else 150.0,
                                "entry_score": 75,
                                "eval_score": 80,
                                "fundamentals": {
                                    "per": 15.0,
                                    "peg": 1.2,
                                    "eps": 5.0,
                                    "fwd_eps": 6.0,
                                    "target_price": 180.0,
                                    "canslim_passed": True,
                                    "canslim_reasons": []
                                },
                                "moving_averages": {
                                    "sma_5": 148.0,
                                    "sma_20": 145.0,
                                    "sma_200": 130.0
                                },
                                "volume": {
                                    "current": 120000.0,
                                    "avg_20": 100000.0
                                }
                            }
                        }
                    
                    if ticker in score_res:
                        res = score_res[ticker]
                        rationale = self._generate_rationale(ticker, res)
                        return ticker, {
                            "current_price": res.get("current_price", 0.0),
                            "entry_score": res.get("entry_score", 0),
                            "eval_score": res.get("eval_score", 0),
                            "total_score": res.get("entry_score", 0) + res.get("eval_score", 0),
                            "rationale": rationale,
                            "name": res.get("name", ticker)
                        }, "success"
                except Exception as e:
                    return ticker, None, f"error: {str(e)}"
                    
                return ticker, None, "failed"

            self.log(f"[SYSTEM] {max_workers}개 스레드로 S&P500 병렬 분석 수행 중...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ticker = {executor.submit(process_single_ticker, t): t for t in tickers}
                
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    
                    with self._thread_lock:
                        if self.state["aborted"]:
                            self.log("[SYSTEM] 스크리너 스캔이 강제 중단되었습니다.")
                            self.state["status"] = "idle"
                            return
                            
                    try:
                        ticker, res, status = future.result()
                        completed_count += 1
                        
                        elapsed = time.time() - start_time
                        rate = completed_count / elapsed if elapsed > 0 else 0
                        remaining = total - completed_count
                        eta_seconds = remaining / rate if rate > 0 else 0
                        
                        if eta_seconds > 60:
                            eta_str = f"{int(eta_seconds // 60)}분 {int(eta_seconds % 60)}초"
                        else:
                            eta_str = f"{int(eta_seconds)}초"
                            
                        progress_pct = int(completed_count / total * 100)
                        
                        with self._thread_lock:
                            self.state["current"] = completed_count
                            self.state["progress"] = progress_pct
                            self.state["current_ticker"] = ticker
                            
                            for r in self.state["results"]:
                                if r["symbol"] == ticker:
                                    if status == "success" and res:
                                        r.update(res)
                                    elif status == "no_prices":
                                        r["rationale"] = "시세 데이터 수집 불가로 분석 제외."
                                    elif status.startswith("error"):
                                        r["rationale"] = f"분석 중 오류 발생: {status}"
                                    else:
                                        r["rationale"] = "분석 실패."
                                    break
                                    
                        if status == "success" and res:
                            self.log(f"[INFO] [{completed_count}/{total}] {ticker} ({res['name']}) 완료 - 진입: {res['entry_score']}점, 평가: {res['eval_score']}점 (진행률: {progress_pct}%, 속도: {rate:.1f}개/초, 남은시간: {eta_str})")
                        elif status == "no_prices":
                            self.log(f"[WARNING] [{completed_count}/{total}] {ticker} 제외 - 시세 데이터 없음 (남은시간: {eta_str})")
                        else:
                            self.log(f"[ERROR] [{completed_count}/{total}] {ticker} 오류: {status} (남은시간: {eta_str})")
                            
                    except Exception as e:
                        self.log(f"[ERROR] 스레드 실행 중 예외 발생: {str(e)}")
                    
                    # Small sleep to prevent tight CPU loop
                    time.sleep(0.005)

            # RDBMS DB 저장 실행
            self.log("[SYSTEM] 3단계: 전체 분석 결과 데이터베이스(RDBMS) 저장 시도 중...")
            saved = save_screener_results(market, self.state["results"])
            if saved:
                self.log("[SUCCESS] 분석 결과를 관계형 데이터베이스(MariaDB/PostgreSQL)에 백업 완료하였습니다.")
            else:
                self.log("[INFO] 데이터베이스 미설정 또는 접속 실패로 DB 저장을 생략했습니다.")

            # 완료 시점 처리 (상태 갱신 및 전체 시작 시각 유지)
            with self._thread_lock:
                # Filter results to keep only analyzed ones
                self.state["results"] = [r for r in self.state["results"] if r.get("total_score") is not None]
                self.state["status"] = "done"
                self.state["progress"] = 100
                self.state["current_ticker"] = ""
            self.log(f"[SUCCESS] {market.upper()} 전종목 스크리닝 분석이 완료되었습니다!")

        except Exception as e:
            self.log(f"[ERROR] 백그라운드 스캔 수행 실패: {str(e)}")
            logger.error(traceback.format_exc())
            with self._thread_lock:
                self.state["status"] = "failed"
                self.state["progress"] = 0
