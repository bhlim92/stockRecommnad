import google.generativeai as genai
from typing import List, Dict, Any, Optional
from app.utils.logger import setup_logger

logger = setup_logger("recommender", "logs/app.log")

class RecommendationEngine:
    """
    Assembles gathered financial signals and generates a detailed investment recommendation report
    using the Gemini LLM.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash") -> None:
        """
        Args:
            api_key: Gemini API developer key.
            model_name: Name of the Gemini model to use.
        """
        self.api_key = api_key
        self.model_name = model_name
        if self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("Gemini API key is missing. Recommendation report will fail or return a template.")

    def generate_recommendation_report(
        self,
        market: Dict[str, Any],
        news: List[Dict[str, Any]],
        youtube: List[Dict[str, Any]],
        canslim: Optional[List[Dict[str, Any]]] = None,
        portfolio: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Constructs system prompts containing market intelligence data and queries Gemini
        to compile a market analysis report in Markdown format.
        
        Returns:
            Markdown-formatted market report.
        """
        if not self.api_key:
            return "# Daily Recommendation Report\n*Warning: Bypassed due to missing Gemini API key.*"

        logger.info("Assembling data and preparing Gemini prompt for daily report...")

        # 1. Format Macro Indicators
        macro_text = ""
        if "macro" in market:
            for k, df in market["macro"].items():
                if isinstance(df, dict):
                    val = df.get("Value", 0.0)
                    date = df.get("Date", "N/A")
                    macro_text += f"- **{k}**: {val:.2f} (as of {date})\n"
                elif not df.empty:
                    val = df["Value"].iloc[-1]
                    date = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1])
                    macro_text += f"- **{k}**: {val:.2f} (as of {date})\n"
        if "yields" in market:
            for k, df in market["yields"].items():
                if isinstance(df, dict):
                    val = df.get("Yield", 0.0)
                    date = df.get("Date", "N/A")
                    macro_text += f"- **{k} Yield**: {val:.2f}% (as of {date})\n"
                elif not df.empty:
                    val = df["Yield"].iloc[-1]
                    date = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1])
                    macro_text += f"- **{k} Yield**: {val:.2f}% (as of {date})\n"
        if "exchange_rates" in market:
            for k, df in market["exchange_rates"].items():
                if isinstance(df, dict):
                    val = df.get("Close", 0.0)
                    macro_text += f"- **{k} Exchange Rate**: {val:.2f}\n"
                elif not df.empty:
                    val = df["Close"].iloc[-1] if "Close" in df.columns else df.iloc[-1, 0]
                    macro_text += f"- **{k} Exchange Rate**: {val:.2f}\n"

        # 2. Format News Items
        news_text = ""
        for i, item in enumerate(news[:15], 1):
            news_text += f"{i}. **{item['title']}** ({item['source']}, {item['pub_date']})\n   *Summary*: {item['summary']}\n"

        # 3. Format YouTube Summaries
        yt_text = ""
        for i, item in enumerate(youtube, 1):
            yt_text += f"### Video {i}: {item['title']}\n"
            yt_text += f"- **Channel**: {item['channel_handle']}\n"
            yt_text += f"- **Published At**: {item['published_at']}\n"
            yt_text += f"- **Link**: {item['link']}\n"
            yt_text += f"- **Summary Insights**:\n{item['llm_summary']}\n\n"

        # 4. Format CANSLIM Scores (if available)
        canslim_text = ""
        if canslim:
            for item in canslim:
                passed_str = "PASSED" if item["passed_screener"] else "FAILED"
                reasons_str = "; ".join(item["reasons"]) if item["reasons"] else "Met all criteria"
                canslim_text += f"- **{item['symbol']}** ({item['name']}): **{passed_str}** | RS Score: {item['rs_score']:.4f} (Rank: {item['rs_rank']}/99) | EPS YoY: {item['eps_growth_yoy']:.1f}% | EPS QoQ: {item['eps_growth_qoq']:.1f}%\n"
                if not item["passed_screener"]:
                    canslim_text += f"  *Exclusion Reasons*: {reasons_str}\n"

        # 5. Format Portfolio & Rebalancing (if available)
        portfolio_text = ""
        if portfolio:
            portfolio_text = f"- **Total Portfolio Valuation**: {portfolio['total_value']:.2f} KRW\n\n"
            portfolio_text += "#### Current Holdings & Weights:\n"
            for h in portfolio["holdings_eval"]:
                pnl_pct = (h['unrealized_pnl'] / h['purchase_value'] * 100.0) if h['purchase_value'] > 0 else 0.0
                portfolio_text += f"- {h['symbol']} ({h['name']}): Class: {h['asset_class']} | Qty: {h['quantity']:.2f} | Current Price: {h['current_price']:.2f} | Value: {h['current_value']:.2f} KRW | Weight: {h['actual_weight']*100:.2f}% | PnL: {h['unrealized_pnl']:.2f} KRW ({pnl_pct:.2f}%)\n"
            
            portfolio_text += f"\n#### Rebalancing Status (Triggered: {portfolio['rebalance_triggered']}):\n"
            for t in portfolio["rebalance_actions"]:
                portfolio_text += f"- **{t['symbol']}** ({t['name']}): Action: **{t['action']}** | Qty Delta: {t['suggested_qty_delta']:.2f} | Current Qty: {t['current_qty']:.2f} | Current Value: {t['current_value']:.2f} KRW | Target Value: {t['target_value']:.2f} KRW | Difference: {t['difference']:.2f} KRW\n"

        # Construct final prompt
        prompt = f"""
You are an Elite Investment Committee AI. Your task is to generate a comprehensive, highly professional, daily investment recommendation report based on the provided macro signals, news, and YouTube expert analyses.

Below is the collected intelligence:

### 1. MACRO ECONOMIC & EXCHANGE DATA
{macro_text}

### 2. TOP MARKET NEWS
{news_text}

### 3. FINANCIAL EXPERT YOUTUBE ANALYSES
{yt_text}
"""

        if canslim_text:
            prompt += f"\n### 4. CANSLIM WATCHLIST SCREENING RESULTS\n{canslim_text}\n"
        if portfolio_text:
            prompt += f"\n### 5. PORTFOLIO STATUS & REBALANCING PLAN\n{portfolio_text}\n"

        prompt += """
---

다음 지침에 맞춰 전문적이고 완성도 높은 한국어 마크다운 보고서(Korean Markdown Report)를 생성해 주세요:
1. **일일 투자 전략 보고서 헤더 (Daily Market Report Header)**: 공식적이고 격식 있는 제목과 오늘 날짜(예: 2026년 6월 1일)를 포함하여 시작해 주세요.
2. **요약 (Executive Summary)**: 수집된 거시 경제 데이터와 뉴스 헤드라인을 결합하여 현재의 시장 국면(예: 강세장 우상향, 변동성 횡보장, 또는 약세장 우하향)과 주요 기회/위험 요인을 한국어로 정밀하게 진단해 주세요.
3. **개별 전문가 영상 요약 (Individual Expert Video Summaries)**: 분석된 각 유튜브 영상에 대해 제목, 채널 핸들명, 링크를 표기하고 아래의 구조화된 요약을 한국어로 작성해 주세요:
   - **시장 및 거시 전망 요약 (Market & Macro Outlook Summary)**: 해당 전문가가 바라보는 시장 방향성과 거시 지표에 대한 견해.
   - **추천 종목 및 섹터 (Buy/Long Recommendations)**: 매수 또는 보유를 추천하는 특정 주식/섹터와 그 이유.
   - **매도 및 주의 종목/섹터 (Sectors & Tickers to Sell/Avoid)**: 매도, 비중 축소 또는 회피/주의를 권고하는 주식/섹터와 그 이유.
   - **핵심 요약 (Core Takeaway)**: 영상의 핵심 논지 요약 (1~2줄).
4. **종합 추천 및 매도 종목/섹터 (Aggregate Sector & Ticker Recommendations)**:
   - 전문가들의 개별 견해를 전체 취합하여 매수/롱 전략을 권고한 **추천 종목 및 섹터 (Buy/Long)**를 깔끔한 마크다운 표로 작성해 주세요. (열 구성: 섹터, 종목명/티커, 추천 사유)
   - 비중 축소, 매도 또는 주의를 권고한 **매도 및 주의 종목/섹터 (Sell/Avoid)**를 깔끔한 마크다운 표로 작성해 주세요. (열 구성: 섹터, 종목명/티커, 사유)

모든 요약과 분석 내용은 명확하고 신뢰감을 주는 금융 분석가 톤(Professional Tone)으로 격식 있게 한국어로 작성해 주세요.
"""

        if canslim_text:
            prompt += "\n5. **Equity Screening & Stock Selection**: Highlight any stocks that passed the CANSLIM screens. If no stock passed strictly, analyze the top-ranked runners-up and explain their strengths and weaknesses.\n"
        if portfolio_text:
            prompt += """\n6. **Asset Allocation & Portfolio Rebalancing Action Plan**:
   - Provide a clean Markdown Table showing: Asset Class, Target Weight, Actual Weight, Deviation, Target Value, Actual Value, and Action (Buy/Sell/Hold).
   - Display a list of concrete, executable trade transactions (rounded integer shares) required to align the portfolio back to the target allocation.
   - Explain the rationale behind the rebalancing.
"""

        prompt += """
7. **Actionable Action Items**: A concise list of 3-5 high-priority next steps for the investor today.

Write the report in a clear, authoritative, professional tone, suitable for high-net-worth investors or fund managers.
"""

        import time
        logger.info("Sleeping 13 seconds to respect Gemini API rate limits...")
        time.sleep(13.0)
        try:
            # Set up model with fallback
            try:
                model = genai.GenerativeModel(self.model_name)
            except Exception:
                model = genai.GenerativeModel("gemini-2.5-flash")

            response = model.generate_content(prompt)
            report = response.text.strip()
            logger.info("Successfully generated daily investment report from Gemini.")
            return report
        except Exception as e:
            logger.error(f"Gemini failed to generate recommendation report: {str(e)}")
            raise e
