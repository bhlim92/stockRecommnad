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
        """Calculate scores for each ticker.

        Parameters
        ----------
        tickers:
            List of ticker symbols (e.g. ``["AAPL", "MSFT"]``).
        preloaded_prices:
            Optional mapping of ticker → ``DataFrame`` containing historic price
            data. When provided the latest close price is extracted for the
            ``current_price`` field; otherwise a yfinance ``history`` call is
            performed.
        """
        results: Dict[str, Dict[str, Any]] = {}
        for ticker in tickers:
            try:
                info = self._fetch_fundamentals(ticker)
                current_price = self._extract_current_price(ticker, preloaded_prices)
                fundamentals = self._parse_fundamentals(info, current_price)
                eval_score = self._calc_fundamental_score(fundamentals, current_price)

                results[ticker] = {
                    "name": info.get("shortName") or ticker,
                    "current_price": current_price,
                    "fundamentals": fundamentals,
                    "entry_score": 0,  # technical entry score is computed elsewhere
                    "eval_score": eval_score,
                    "moving_averages": {},
                    "volume": {},
                }
            except Exception as exc:  # pragma: no cover – defensive logging
                self.logger.exception("Failed to calculate scores for %s", ticker)
                continue
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
