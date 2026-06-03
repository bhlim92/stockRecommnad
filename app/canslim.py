import pandas as pd
import yfinance as yf
from typing import List, Dict, Tuple, Optional, TypedDict
from app.utils.logger import setup_logger

logger = setup_logger("canslim", "logs/app.log")

class CanslimScore(TypedDict):
    """Result of running a ticker through CANSLIM criteria"""
    symbol: str
    name: str
    eps_growth_yoy: float
    eps_growth_qoq: float
    near_52w_high: bool
    volume_above_average: bool
    rs_score: float
    rs_rank: int
    passed_screener: bool
    reasons: List[str]

class CanslimScreener:
    """
    Evaluates individual stocks based on modified CANSLIM rules, verifying EPS trends,
    relative market strengths, volumes, and proximity to high marks.
    """

    def __init__(self, data_fetcher: any) -> None:
        """
        Args:
            data_fetcher: An instance of AssetDataFetcher.
        """
        self.fetcher = data_fetcher

    def _extract_eps_or_net_income(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """Extracts EPS or Net Income row from financials DataFrame."""
        if df.empty:
            return None
        
        # Check standard labels
        for label in ["Basic EPS", "Diluted EPS", "BasicEPS", "DilutedEPS"]:
            matching = [idx for idx in df.index if idx.lower() == label.lower()]
            if matching:
                return df.loc[matching[0]]
                
        # Fallback to Net Income
        for label in ["Net Income", "NetIncome", "Net Income Common Stockholders"]:
            matching = [idx for idx in df.index if idx.lower() == label.lower()]
            if matching:
                return df.loc[matching[0]]
                
        # Generic fallback
        for idx in df.index:
            if "eps" in idx.lower() or "net income" in idx.lower() or "netincome" in idx.lower():
                return df.loc[idx]
                
        return None

    def evaluate_growth_rate(self, ticker: str) -> Tuple[float, float]:
        """
        Calculates EPS YoY and QoQ growth percentage.
        
        Args:
            ticker: Stock symbol.
            
        Returns:
            Tuple of (YoY EPS growth rate %, QoQ EPS growth rate %).
        """
        logger.info(f"Evaluating quarterly earnings growth rate for {ticker}")
        try:
            ticker_obj = yf.Ticker(ticker)
            q_fin = ticker_obj.quarterly_financials
            if q_fin.empty:
                q_fin = ticker_obj.quarterly_income_stmt
                
            if q_fin.empty:
                logger.warning(f"No quarterly financials found for {ticker}")
                return (0.0, 0.0)

            # Extract series
            series = self._extract_eps_or_net_income(q_fin)
            if series is None or len(series) == 0:
                logger.warning(f"No EPS or Net Income series extracted for {ticker}")
                return (0.0, 0.0)
                
            # Ensure index is sorted descending (newest first)
            series = series.sort_index(ascending=False)
            newest_date = series.index[0]
            newest_val = float(series.iloc[0])
            
            yoy_quarter_value = None
            qoq_quarter_value = None

            # Attempt date-based lookup
            for date_idx, val in series.items():
                try:
                    diff_days = (newest_date - date_idx).days
                    if 340 <= diff_days <= 390:
                        yoy_quarter_value = float(val)
                    if 70 <= diff_days <= 110:
                        qoq_quarter_value = float(val)
                except Exception:
                    continue

            # Fallback to index-based lookup if dates are not parseable
            if yoy_quarter_value is None and len(series) >= 5:
                yoy_quarter_value = float(series.iloc[4])
            if qoq_quarter_value is None and len(series) >= 2:
                qoq_quarter_value = float(series.iloc[1])

            # Calculate growth rates
            if yoy_quarter_value is not None and yoy_quarter_value != 0:
                eps_growth_yoy = ((newest_val - yoy_quarter_value) / abs(yoy_quarter_value)) * 100.0
            else:
                eps_growth_yoy = 0.0

            if qoq_quarter_value is not None and qoq_quarter_value != 0:
                eps_growth_qoq = ((newest_val - qoq_quarter_value) / abs(qoq_quarter_value)) * 100.0
            else:
                eps_growth_qoq = 0.0

            return (eps_growth_yoy, eps_growth_qoq)
        except Exception as e:
            logger.warning(f"Failed to evaluate growth rate for {ticker}: {str(e)}")
            return (0.0, 0.0)

    def evaluate_annual_and_roe(self, ticker: str) -> Tuple[bool, Optional[float], List[str]]:
        """
        Evaluates annual EPS growth (last 3 years) and ROE.
        
        Returns:
            Tuple of (passed_annual_screener, ROE_value, warnings/reasons).
        """
        reasons = []
        try:
            ticker_obj = yf.Ticker(ticker)
            ann_fin = ticker_obj.financials
            if ann_fin.empty:
                ann_fin = ticker_obj.income_stmt
                
            ann_bs = ticker_obj.balance_sheet
            
            if ann_fin.empty:
                return (False, None, ["No annual financials found"])
                
            # Extract Annual series
            series = self._extract_eps_or_net_income(ann_fin)
            if series is None or len(series) < 4:
                return (False, None, [f"Insufficient annual history (need 4 years, got {len(series) if series is not None else 0})"])

            series = series.sort_index(ascending=False)
            
            # Check 3 years of growth (Y1 vs Y2, Y2 vs Y3, Y3 vs Y4)
            growth_rates = []
            for i in range(3):
                curr = float(series.iloc[i])
                prior = float(series.iloc[i+1])
                if prior != 0:
                    growth = ((curr - prior) / abs(prior)) * 100.0
                else:
                    growth = 0.0
                growth_rates.append(growth)
                
            annual_pass = all(g >= 20.0 for g in growth_rates)
            if not annual_pass:
                reasons.append(f"Annual EPS growth rates were { [f'{g:.1f}%' for g in growth_rates] } (need >=20% for 3 years)")

            # ROE calculation
            roe = None
            if not ann_bs.empty:
                net_income = float(series.iloc[0])
                equity_series = None
                for label in ["Stockholders Equity", "Total Stockholders Equity", "Shareholders Equity", "Total Equity", "Common Stock Equity"]:
                    matching = [idx for idx in ann_bs.index if idx.lower() == label.lower()]
                    if matching:
                        equity_series = ann_bs.loc[matching[0]]
                        break
                        
                if equity_series is not None and len(equity_series) > 0:
                    equity_series = equity_series.sort_index(ascending=False)
                    equity = float(equity_series.iloc[0])
                    if equity != 0:
                        roe = (net_income / equity) * 100.0
                        if roe < 17.0:
                            reasons.append(f"ROE of {roe:.1f}% was below 17%")
                    else:
                        reasons.append("Shareholders Equity was zero, cannot calc ROE")
                else:
                    reasons.append("Could not find Shareholders Equity in Balance Sheet")
            else:
                reasons.append("No Balance Sheet found for ROE calculation")

            passed = annual_pass and (roe is not None and roe >= 17.0)
            return (passed, roe, reasons)
        except Exception as e:
            logger.warning(f"Error checking annual financials/ROE for {ticker}: {str(e)}")
            return (False, None, [f"Error checking annual data: {str(e)}"])

    def calculate_relative_strength(self, tickers: List[str]) -> Dict[str, Tuple[float, int]]:
        """
        Computes Relative Strength (RS) scores and ranks for a list of stocks.
        
        Formula: RS Raw = 0.4 * R_Q1 + 0.2 * R_Q2 + 0.2 * R_Q3 + 0.2 * R_Q4
        
        Args:
            tickers: List of ticker symbols.
            
        Returns:
            Dictionary matching tickers to tuple of (raw_rs_score, rs_percentile_rank 1-99).
        """
        logger.info("Calculating Relative Strength rating for watchlist tickers")
        raw_scores = {}
        
        for ticker in tickers:
            try:
                # Fetch 1 year of daily historical price data
                df = self.fetcher.fetch_historical_prices(ticker, period="1y", interval="1d")
                if df.empty or len(df) < 200:
                    logger.warning(f"Insufficient history for RS calculation of {ticker}")
                    raw_scores[ticker] = 0.0
                    continue
                
                # Fetch closing prices
                closes = df["Close"]
                p_0 = float(closes.iloc[-1])
                
                # Find positions approx 3, 6, 9, 12 months ago
                n = len(closes)
                p_3m = float(closes.iloc[-63]) if n >= 63 else float(closes.iloc[0])
                p_6m = float(closes.iloc[-126]) if n >= 126 else float(closes.iloc[0])
                p_9m = float(closes.iloc[-189]) if n >= 189 else float(closes.iloc[0])
                p_12m = float(closes.iloc[0])
                
                # Calculate returns
                r_q1 = (p_0 - p_3m) / p_3m if p_3m != 0 else 0.0
                r_q2 = (p_3m - p_6m) / p_6m if p_6m != 0 else 0.0
                r_q3 = (p_6m - p_9m) / p_9m if p_9m != 0 else 0.0
                r_q4 = (p_9m - p_12m) / p_12m if p_12m != 0 else 0.0
                
                # Weighted RS Raw Score
                rs_raw = 0.4 * r_q1 + 0.2 * r_q2 + 0.2 * r_q3 + 0.2 * r_q4
                raw_scores[ticker] = rs_raw
            except Exception as e:
                logger.warning(f"Error calculating raw RS score for {ticker}: {str(e)}")
                raw_scores[ticker] = 0.0

        # Calculate percentile ranks (1 to 99)
        sorted_tickers = sorted(raw_scores.items(), key=lambda x: x[1])
        n = len(sorted_tickers)
        rs_results = {}
        for rank_idx, (ticker, raw_score) in enumerate(sorted_tickers, start=1):
            if n > 1:
                # Standardize to 1-99 range
                pct = 1.0 + (rank_idx - 1) / (n - 1) * 98.0
            else:
                pct = 99.0
            rs_results[ticker] = (raw_score, int(round(pct)))
            
        return rs_results

    def _check_market_direction(self) -> Tuple[bool, bool]:
        """
        Checks if S&P 500 (^GSPC) and KOSPI (^KS11) are trading above their 50D and 200D SMAs.
        
        Returns:
            Tuple of (US market is in uptrend (bool), KR market is in uptrend (bool)).
        """
        def check_index(ticker: str) -> bool:
            try:
                # Fetch 1 year data to cover 200 trading days
                df = self.fetcher.fetch_historical_prices(ticker, period="1y", interval="1d")
                if df.empty or len(df) < 200:
                    return False
                
                closes = df["Close"]
                current_price = float(closes.iloc[-1])
                
                sma_50 = float(closes.iloc[-50:].mean())
                sma_200 = float(closes.iloc[-200:].mean())
                
                # Uptrend conditions
                return current_price > sma_50 and sma_50 > sma_200
            except Exception as e:
                logger.warning(f"Failed to check market index {ticker}: {str(e)}")
                return False

        us_uptrend = check_index("^GSPC")
        kr_uptrend = check_index("^KS11")
        return us_uptrend, kr_uptrend

    def screen_watchlist(self, watchlist: List[str]) -> List[CanslimScore]:
        """
        Runs full screening logic across target list of tickers.
        
        Args:
            watchlist: Target symbols to screen.
            
        Returns:
            List of results matching CanslimScore structure.
        """
        logger.info(f"Running CANSLIM screening for watchlist of {len(watchlist)} tickers")
        
        # 1. Compute Relative Strength Rankings
        rs_ratings = self.calculate_relative_strength(watchlist)
        
        # 2. Check Market Trends
        us_uptrend, kr_uptrend = self._check_market_direction()
        logger.info(f"Market Trends: US Uptrend = {us_uptrend}, KR Uptrend = {kr_uptrend}")

        scores: List[CanslimScore] = []
        
        for ticker in watchlist:
            try:
                reasons = []
                passed = True
                
                # Fetch daily data for N and S
                df = self.fetcher.fetch_historical_prices(ticker, period="1y", interval="1d")
                if df.empty:
                    logger.warning(f"Skipping {ticker}: No price history found")
                    continue
                
                # Retrieve names via yfinance Ticker info
                try:
                    name = yf.Ticker(ticker).info.get("longName", ticker)
                except Exception:
                    name = ticker

                closes = df["Close"]
                volumes = df["Volume"]
                
                current_price = float(closes.iloc[-1])
                current_volume = float(volumes.iloc[-1])
                
                # C & A: Quarterly & Annual EPS + ROE
                eps_growth_yoy, eps_growth_qoq = self.evaluate_growth_rate(ticker)
                
                # Strict check C: Current Quarterly EPS Growth >= 20%
                if eps_growth_yoy < 20.0:
                    passed = False
                    reasons.append(f"C: Quarterly EPS YoY growth {eps_growth_yoy:.1f}% was below 20%")

                # Strict check A: Annual growth & ROE
                annual_pass, roe_val, ann_reasons = self.evaluate_annual_and_roe(ticker)
                if not annual_pass:
                    passed = False
                    reasons.extend([f"A: {r}" for r in ann_reasons])

                # N: Within 15% of 52-week High
                price_52w_high = float(closes.max())
                near_52w_high = current_price >= (0.85 * price_52w_high)
                if not near_52w_high:
                    passed = False
                    reasons.append(f"N: Price ({current_price:.2f}) is not within 15% of 52W High ({price_52w_high:.2f})")

                # S: Volume confirmation
                # Calculate 50D average volume (excluding the current day)
                sma_volume_50 = float(volumes.iloc[-51:-1].mean()) if len(volumes) >= 51 else float(volumes.mean())
                volume_above_average = current_volume > sma_volume_50
                
                # Check price change on current day
                prev_price = float(closes.iloc[-2]) if len(closes) >= 2 else current_price
                price_change_pct = ((current_price - prev_price) / prev_price) * 100.0 if prev_price != 0 else 0.0
                
                # If price increases by >= 2%, check volume > average
                if price_change_pct >= 2.0 and not volume_above_average:
                    passed = False
                    reasons.append(f"S: Price increased {price_change_pct:.1f}% but Volume was below 50D average")

                # L: Relative Strength Rank >= 70
                raw_rs, rs_rank = rs_ratings.get(ticker, (0.0, 1))
                if rs_rank < 70:
                    passed = False
                    reasons.append(f"L: RS Percentile Rank {rs_rank} is below 70")

                # I: Institutional ownership check (Proxy)
                try:
                    inst_pct = yf.Ticker(ticker).info.get("institutionalPercentHeld")
                    if inst_pct is not None:
                        inst_pct_val = inst_pct * 100.0
                        if inst_pct_val < 30.0:
                            passed = False
                            reasons.append(f"I: Institutional ownership {inst_pct_val:.1f}% is below 30%")
                except Exception as e:
                    # Ignore or warn, but do not fail
                    logger.debug(f"Could not fetch inst ownership for {ticker}: {str(e)}")

                # M: Market trend index SMA checks
                is_korean = ticker.endswith(".KS") or ticker.endswith(".KQ") or (ticker.isdigit() and len(ticker) == 6)
                market_uptrend = kr_uptrend if is_korean else us_uptrend
                if not market_uptrend:
                    passed = False
                    reasons.append("M: Market index is not in confirmed uptrend (below 50D or 50D below 200D)")

                scores.append({
                    "symbol": ticker,
                    "name": name,
                    "eps_growth_yoy": eps_growth_yoy,
                    "eps_growth_qoq": eps_growth_qoq,
                    "near_52w_high": near_52w_high,
                    "volume_above_average": volume_above_average,
                    "rs_score": raw_rs,
                    "rs_rank": rs_rank,
                    "passed_screener": passed,
                    "reasons": reasons
                })
                logger.info(f"Ticker {ticker} evaluated. Passed CANSLIM: {passed}. Reasons: {reasons}")
            except Exception as e:
                logger.error(f"Error screening ticker {ticker}: {str(e)}")
                # If error, we still add with passed_screener = False
                scores.append({
                    "symbol": ticker,
                    "name": ticker,
                    "eps_growth_yoy": 0.0,
                    "eps_growth_qoq": 0.0,
                    "near_52w_high": False,
                    "volume_above_average": False,
                    "rs_score": 0.0,
                    "rs_rank": 1,
                    "passed_screener": False,
                    "reasons": [f"Execution error: {str(e)}"]
                })
                
        return scores
