import logging
from typing import List, Dict, Any, Optional
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


class QuantScorer:
    """Calculate quantitative scores for a list of ticker symbols.

    The scoring logic uses the following financial fields retrieved from the
    yfinance ``Ticker.info`` endpoint:

    - ``trailingPE``   : PER (price‑earnings ratio, TTM)
    - ``pegRatio``     : PEG (PER / 5‑year EPS growth)
    - ``trailingEps``  : EPS (TTM)
    - ``forwardEps``   : Forward EPS (next 12‑months)
    - ``targetMeanPrice`` : Analyst consensus target price
    - ``passed_screener`` / ``reasons`` : CANSLIM filter result (bool + list)

    The module provides a **QuantScorer** class with a single public method
    ``calculate_scores`` that returns a dict keyed by ticker symbol. Each entry
    contains:

    ```json
    {
        "name": "Company name",
        "current_price": 123.45,
        "fundamentals": {
            "per": 15.2,
            "peg": 1.3,
            "eps": 3.42,
            "fwd_eps": 4.10,
            "target_price": 150.0,
            "canslim_passed": true,
            "canslim_reasons": ["..."]
        },
        "entry_score": 0,               # placeholder – technical part handled elsewhere
        "eval_score": 78,               # composite fundamental score (0‑100)
        "moving_averages": {},          # reserved for future technical data
        "volume": {}
    }
    ```

    The scores are *relative* (0‑100) and are calculated using simple heuristics
    that prioritize low valuation (PER, PEG), EPS growth, and analyst upside.
    ````
    """

    def __init__(self):
        self.logger = logger

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def calculate_scores(
        self,
        tickers: List[str],
        preloaded_prices: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate scores for each ticker using concurrent threads to speed up yfinance info queries."""
        results: Dict[str, Dict[str, Any]] = {}
        if not tickers:
            return results

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def process_ticker(ticker: str) -> Optional[Dict[str, Any]]:
            try:
                info = self._fetch_fundamentals(ticker)
                current_price = self._extract_current_price(ticker, preloaded_prices)
                fundamentals = self._parse_fundamentals(info, current_price)
                eval_score = self._calc_fundamental_score(fundamentals, current_price)
                
                # Check for moving averages and volume if preloaded prices are available
                ma = {}
                vol = {}
                entry_details = []
                eval_details = []
                entry_score = 0
                
                if preloaded_prices and ticker in preloaded_prices:
                    df = preloaded_prices[ticker]
                    
                    # Handle MultiIndex if present (safe check for Ticker vs Attribute levels)
                    if isinstance(df.columns, pd.MultiIndex):
                        df = df.copy()
                        known_attrs = {"Close", "Open", "Volume", "High", "Low", "Adj Close"}
                        new_columns = []
                        for col_tuple in df.columns:
                            matched = False
                            for part in col_tuple:
                                if part in known_attrs:
                                    new_columns.append(part)
                                    matched = True
                                    break
                            if not matched:
                                new_columns.append(col_tuple[-1] if col_tuple else "")
                        df.columns = new_columns
                        
                    if all(col in df.columns for col in ["Close", "Open", "Volume"]):
                        closes = df["Close"]
                        opens = df["Open"]
                        volumes = df["Volume"]
                        
                        if len(df) >= 200:
                            ma["sma_200"] = float(closes.rolling(200).mean().iloc[-1])
                        if len(df) >= 20:
                            ma["sma_20"] = float(closes.rolling(20).mean().iloc[-1])
                            vol["avg_20"] = float(volumes.rolling(20).mean().iloc[-1])
                        if len(df) >= 5:
                            ma["sma_5"] = float(closes.rolling(5).mean().iloc[-1])
                        if len(df) >= 1:
                            vol["current"] = float(volumes.iloc[-1])

                        # Calculate technical entry score if we have at least 200 days of data
                        if len(df) >= 200:
                            # 1. S1: Moving Averages Alignment
                            sma_5_val = ma["sma_5"]
                            sma_20_val = ma["sma_20"]
                            sma_200_val = ma["sma_200"]
                            
                            if sma_5_val > sma_20_val > sma_200_val:
                                s1 = 1.0
                                entry_details.append("5/20/200일선 정배열 (우상향)")
                            elif sma_5_val < sma_20_val < sma_200_val:
                                s1 = -1.0
                                entry_details.append("5/20/200일선 역배열 (우하향)")
                            else:
                                s1 = 0.0
                                entry_details.append("이평선 혼조세 (횡보)")
                                
                            # 2. S2: MACD Crossover
                            ema_12 = closes.ewm(span=12, adjust=False).mean()
                            ema_26 = closes.ewm(span=26, adjust=False).mean()
                            macd = ema_12 - ema_26
                            signal = macd.ewm(span=9, adjust=False).mean()
                            
                            if len(macd) >= 2:
                                macd_today = float(macd.iloc[-1])
                                signal_today = float(signal.iloc[-1])
                                macd_yest = float(macd.iloc[-2])
                                signal_yest = float(signal.iloc[-2])
                                
                                if pd.isna(macd_today) or pd.isna(signal_today) or pd.isna(macd_yest) or pd.isna(signal_yest):
                                    s2 = 0.0
                                elif macd_yest <= signal_yest and macd_today > signal_today and macd_today > 0:
                                    s2 = 1.0
                                    entry_details.append("MACD 골든크로스 감지")
                                elif macd_yest >= signal_yest and macd_today < signal_today:
                                    s2 = -1.0
                                    entry_details.append("MACD 데드크로스 감지")
                                else:
                                    s2 = 0.0
                            else:
                                s2 = 0.0
                                
                            # 3. S3: Pullback RSI (14 days)
                            delta = closes.diff()
                            gain = delta.where(delta > 0, 0.0)
                            loss = -delta.where(delta < 0, 0.0)
                            avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                            avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                            
                            if len(avg_gain) >= 1 and len(avg_loss) >= 1:
                                avg_gain_val = float(avg_gain.iloc[-1])
                                avg_loss_val = float(avg_loss.iloc[-1])
                                
                                if pd.isna(avg_gain_val) or pd.isna(avg_loss_val):
                                    rsi_today = 50.0
                                elif avg_loss_val == 0 and avg_gain_val == 0:
                                    rsi_today = 50.0
                                elif avg_loss_val == 0:
                                    rsi_today = 100.0
                                elif avg_gain_val == 0:
                                    rsi_today = 0.0
                                else:
                                    rs = avg_gain_val / avg_loss_val
                                    rsi_today = 100.0 - (100.0 / (1.0 + rs))
                            else:
                                rsi_today = 50.0
                                
                            if s1 == 1.0 and 40.0 <= rsi_today <= 50.0:
                                s3 = 1.0
                                entry_details.append("상승장 RSI 눌림목 조정 완료")
                            elif rsi_today > 80.0:
                                s3 = -1.0
                                entry_details.append("RSI 과매수 경계 진입")
                            else:
                                s3 = 0.0
                                
                            # 4. S4: Volume
                            avg_vol_20 = vol.get("avg_20", 0.0)
                            current_vol = vol.get("current", 0.0)
                            current_close = float(closes.iloc[-1])
                            current_open = float(opens.iloc[-1])
                            
                            if (pd.isna(avg_vol_20) or pd.isna(current_vol) or 
                                pd.isna(current_close) or pd.isna(current_open) or 
                                avg_vol_20 <= 0):
                                s4 = 0.0
                            elif current_vol >= 1.5 * avg_vol_20 and current_close > current_open:
                                s4 = 1.0
                                entry_details.append("거래량 수반 돌파 양봉 감지")
                            else:
                                s4 = 0.0
                                
                            # Final Score & Mapping to 0-100 scale (int((FS + 1.0) * 50))
                            final_score = (0.4 * s1) + (0.3 * s2) + (0.2 * s3) + (0.1 * s4)
                            entry_score = int((final_score + 1.0) * 50 + 1e-9)
                            entry_score = max(0, min(100, entry_score))
                        else:
                            entry_details.append("기술 지표 데이터 부족 (200일 미만)")
                    else:
                        entry_details.append("기술 지표 데이터 구조 오류 (필수 컬럼 누락)")
                else:
                    entry_details.append("기술 지표 데이터 대기")

                # Basic fundamental details populator
                per = fundamentals.get("per")
                if per is not None:
                    eval_details.append(f"PER: {per:.1f}")
                peg = fundamentals.get("peg")
                if peg is not None:
                    eval_details.append(f"PEG: {peg:.1f}")
                if fundamentals.get("canslim_passed"):
                    eval_details.append("CANSLIM 통과")

                return {
                    "name": info.get("shortName") or ticker,
                    "current_price": current_price,
                    "fundamentals": fundamentals,
                    "entry_score": entry_score,
                    "eval_score": eval_score,
                    "moving_averages": ma,
                    "volume": vol,
                    "entry_details": entry_details,
                    "eval_details": eval_details,
                }
            except Exception as exc:  # pragma: no cover – defensive logging
                self.logger.exception("Failed to calculate scores for %s", ticker)
                return None

        max_workers = min(15, len(tickers))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {executor.submit(process_ticker, t): t for t in tickers}
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    if data is not None:
                        results[ticker] = data
                except Exception as exc:
                    self.logger.exception("Failed to retrieve future result for %s", ticker)

        return results

    # ---------------------------------------------------------------------
    # Helper methods – one per logical step
    # ---------------------------------------------------------------------
    def _fetch_fundamentals(self, ticker: str) -> Dict[str, Any]:
        """Retrieve the raw ``info`` dict from yfinance.

        The method isolates the network request to a single place so that unit
        tests can monkey‑patch it if needed.
        """
        yf_ticker = yf.Ticker(ticker)
        return yf_ticker.info

    def _extract_current_price(
        self,
        ticker: str,
        preloaded_prices: Optional[Dict[str, pd.DataFrame]],
    ) -> float:
        """Return the most recent ``Close`` price.

        If a pre‑loaded price frame is supplied we use its last row; otherwise we
        request a single‑day history from yfinance.
        """
        if preloaded_prices and ticker in preloaded_prices:
            df = preloaded_prices[ticker]
            if not df.empty:
                # Handle MultiIndex if present
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.copy()
                    known_attrs = {"Close", "Open", "Volume", "High", "Low", "Adj Close"}
                    new_columns = []
                    for col_tuple in df.columns:
                        matched = False
                        for part in col_tuple:
                            if part in known_attrs:
                                new_columns.append(part)
                                matched = True
                                break
                        if not matched:
                            new_columns.append(col_tuple[-1] if col_tuple else "")
                    df.columns = new_columns
                return float(df["Close"].iloc[-1])
        # Fallback – retrieve the latest price via ``fast_info`` when available
        try:
            fast_info = yf.Ticker(ticker).fast_info
            price = fast_info.get("last_price")
            if price is not None:
                return float(price)
        except Exception:
            pass
        # Last resort – use ``history`` for one day
        df = yf.Ticker(ticker).history(period="1d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
        return 0.0

    def _parse_fundamentals(self, info: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """Extract the fields required for the scoring model.

        Missing values are normalised to ``None`` so that the scoring routine can
        handle them gracefully.
        """
        fundamentals = {
            "per": info.get("trailingPE"),
            "peg": info.get("pegRatio"),
            "eps": info.get("trailingEps"),
            "fwd_eps": info.get("forwardEps"),
            "target_price": info.get("targetMeanPrice"),
            "canslim_passed": info.get("passed_screener"),
            "canslim_reasons": info.get("reasons"),
        }
        fundamentals["current_price"] = current_price
        return fundamentals

    def _calc_fundamental_score(self, fundamentals: Dict[str, Any], current_price: float) -> int:
        """Combine individual metrics into a 0‑100 score.

        Weight distribution (total 100 pts):
        - PER (30 pts) – lower PER yields higher points; PER > 30 → 0 pts.
        - PEG (20 pts) – lower PEG is better; PEG > 2 → 0 pts.
        - EPS growth (20 pts) – ((fwd_eps‑eps)/|eps|) × 100 % capped at 50 %.
        - Analyst upside (15 pts) – ((target‑current)/current) × 100 % capped at 30 %.
        - CANSLIM pass (15 pts) – binary flag.
        """
        score = 0
        # PER – best when < 10, linearly decreasing to 0 at 30
        per = fundamentals.get("per")
        if isinstance(per, (int, float)):
            if per <= 10:
                score += 30
            elif per < 30:
                score += int(30 * (30 - per) / 20)
        # PEG – best when < 1, linearly decreasing to 0 at 2
        peg = fundamentals.get("peg")
        if isinstance(peg, (int, float)):
            if peg <= 1:
                score += 20
            elif peg < 2:
                score += int(20 * (2 - peg) / 1)
        # EPS growth
        eps = fundamentals.get("eps")
        fwd_eps = fundamentals.get("fwd_eps")
        if isinstance(eps, (int, float)) and eps != 0 and isinstance(fwd_eps, (int, float)):
            growth_pct = ((fwd_eps - eps) / abs(eps)) * 100
            if growth_pct >= 20:
                score += 20
            elif growth_pct > 0:
                score += int(20 * growth_pct / 20)
        # Analyst upside – (target‑current)/current × 100 %
        target = fundamentals.get("target_price")
        if isinstance(target, (int, float)) and target > 0 and current_price > 0:
            upside_pct = ((target - current_price) / current_price) * 100
            if upside_pct >= 20:
                score += 15
            elif upside_pct > 0:
                score += int(15 * upside_pct / 20)
        # CANSLIM pass flag
        if fundamentals.get("canslim_passed"):
            score += 15
        return max(0, min(100, score))

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}()"
