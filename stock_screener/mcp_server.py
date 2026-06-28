"""MCP server interface for the Stock Screener application."""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.contrib.mcp_mixin import MCPMixin
from fastmcp.contrib.mcp_mixin import mcp_tool
from fastmcp.contrib.mcp_mixin import mcp_prompt

from stock_screener.cache import IndustryAverageCache
from stock_screener.industry import IndustryAverageProvider
from stock_screener.industry import resolve_industry_averages
from stock_screener.parser import HtmlParser
from stock_screener.ratios import RatioInfo
from stock_screener.ratios import RatioConfigResolver
from stock_screener.scorer import Scorer
from stock_screener.scraper import ScrapeError
from stock_screener.scraper import FinvizScraper


class StockScreenerMcpServer(MCPMixin):
    """MCP server that exposes stock screening tools and prompts."""

    VALID_STOCK_TYPES: list[str] = ["div", "growth", "value"]

    def __init__(self) -> None:
        self._ratio_resolver: RatioConfigResolver = RatioConfigResolver()
        self._scorer: Scorer = Scorer()

    @staticmethod
    def _parse_stock_types(raw: str) -> list[str]:
        """Split comma-separated stock types, deduplicate, and validate.

        Returns a list of unique, validated stock type strings.
        Raises ValueError if any type is invalid.
        """
        parts: list[str] = [part.strip() for part in raw.split(",")]
        unique: list[str] = list(dict.fromkeys(parts))

        for stock_type in unique:
            if stock_type not in StockScreenerMcpServer.VALID_STOCK_TYPES:
                raise ValueError(
                    f"Unknown stock type '{stock_type}'. "
                    f"Valid types: {StockScreenerMcpServer.VALID_STOCK_TYPES}"
                )

        return unique

    @staticmethod
    def _resolve_api_key(api_key: str) -> str | None:
        """Return the API key from the parameter or environment variable."""
        if api_key:
            return api_key
        return os.environ.get("OPENAI_API_KEY")

    def _process_stock_type(
        self,
        stock_type: str,
        parser: HtmlParser,
        provider: IndustryAverageProvider,
        cache: IndustryAverageCache,
        use_cache: bool,
        refresh: bool,
        ticker: str,
        sector: str,
        industry: str,
    ) -> dict[str, Any]:
        """Process a single stock type and return a structured dict.

        Returns a dict with type, score, max_score, and ratios list.
        """
        ratio_set: list[RatioInfo] = (
            self._ratio_resolver.get_ratio_set(stock_type)
        )
        values: dict[str, str] = parser.parse_ratios(ratio_set)

        industry_averages: dict[str, str] = resolve_industry_averages(
            provider, cache, ticker, stock_type, ratio_set,
            sector, industry, use_cache, refresh,
        )

        score: int
        max_score: int
        score, max_score = self._scorer.score_ratios(
            ratio_set, values, industry_averages, stock_type
        )

        ratios: list[dict[str, str]] = [
            {
                "name": ratio.name,
                "optimal": ratio.optimal,
                "industry_average": industry_averages.get(ratio.name, "N/A"),
                "realtime_value": values.get(ratio.name, "N/A"),
                "importance": ratio.importance,
            }
            for ratio in ratio_set
        ]

        return {
            "type": stock_type,
            "score": score,
            "max_score": max_score,
            "ratios": ratios,
        }

    def _validate_inputs(
        self,
        api_key: str,
        stock_type: str,
        no_cache: bool,
        refresh: bool,
    ) -> tuple[str, list[str]] | dict[str, str]:
        """Validate inputs and return (resolved_key, stock_types) or error dict."""
        if no_cache and refresh:
            return {
                "error": (
                    "The 'no_cache' and 'refresh' options are mutually "
                    "exclusive. Provide only one."
                )
            }

        resolved_key: str | None = self._resolve_api_key(api_key)
        if resolved_key is None:
            return {
                "error": (
                    "No API key provided. Pass 'api_key' or set the "
                    "OPENAI_API_KEY environment variable."
                )
            }

        try:
            stock_types: list[str] = self._parse_stock_types(stock_type)
        except ValueError as exc:
            return {"error": str(exc)}

        return (resolved_key, stock_types)

    def _fetch_and_parse(
        self,
        ticker: str,
    ) -> tuple[str, HtmlParser, str, str, str] | dict[str, str]:
        """Fetch finviz page and parse price/sector/industry.

        Returns (html, parser, price, sector, industry) or error dict.
        """
        scraper: FinvizScraper = FinvizScraper()
        try:
            html: str = scraper.fetch_page(ticker)
        except ScrapeError as exc:
            return {"error": exc.message}

        try:
            parser: HtmlParser = HtmlParser(html)
            price: str = parser.parse_price()
            sector: str
            industry_name: str
            sector, industry_name = parser.parse_sector_industry()
        except (AttributeError, IndexError, TypeError) as exc:
            return {"error": f"Error parsing HTML: {exc}"}

        return (html, parser, price, sector, industry_name)

    @mcp_tool(
        name="stock_screener",
        description="Screen a stock by ticker and type(s).",
    )
    def stock_screener(
        self,
        ticker: str,
        stock_type: str,
        api_key: str = "",
        no_cache: bool = False,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Screen a stock by ticker and type(s).

        Args:
            ticker: Stock ticker symbol (e.g. AAPL, MSFT).
            stock_type: Comma-separated stock types: div, growth, value.
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            no_cache: Disable cache entirely — no reading or writing.
            refresh: Ignore cached data but write fresh results to cache.

        Returns a dict with ticker, price, sector, industry,
        per-type ratio data with scores, and cumulative investment score.
        Returns a dict with an "error" key on failure.
        """
        validation: tuple[str, list[str]] | dict[str, str] = self._validate_inputs(
            api_key, stock_type, no_cache, refresh
        )
        if isinstance(validation, dict):
            return validation
        resolved_key: str = validation[0]
        stock_types: list[str] = validation[1]

        normalized_ticker: str = ticker.upper()

        fetch_result: tuple[str, HtmlParser, str, str, str] | dict[str, str] = (
            self._fetch_and_parse(normalized_ticker)
        )
        if isinstance(fetch_result, dict):
            return fetch_result
        parser: HtmlParser = fetch_result[1]
        price: str = fetch_result[2]
        sector: str = fetch_result[3]
        industry_name: str = fetch_result[4]

        provider: IndustryAverageProvider = IndustryAverageProvider(
            resolved_key
        )
        cache: IndustryAverageCache = IndustryAverageCache()
        use_cache: bool = not no_cache

        total_score: int = 0
        total_max: int = 0
        type_results: list[dict[str, Any]] = []

        for st in stock_types:
            try:
                result: dict[str, Any] = self._process_stock_type(
                    st, parser, provider, cache, use_cache,
                    refresh, normalized_ticker, sector, industry_name,
                )
                total_score += result["score"]
                total_max += result["max_score"]
                type_results.append(result)
            except ValueError as exc:
                return {"error": str(exc)}

        percentage: float = (
            (total_score / total_max * 100.0) if total_max > 0 else 0.0
        )

        return {
            "ticker": normalized_ticker,
            "price": price,
            "sector": sector,
            "industry": industry_name,
            "stock_types": type_results,
            "total_score": total_score,
            "total_max": total_max,
            "percentage": round(percentage, 1),
        }

    @mcp_tool(
        name="get_ratio_definitions",
        description="Get the ratio definitions for a stock type.",
    )
    def get_ratio_definitions(self, stock_type: str) -> dict[str, Any]:
        """Get the ratio definitions for a stock type.

        Args:
            stock_type: One of: div, growth, value.

        Returns a dict with the stock_type and a list of ratio definitions,
        each containing name, optimal, importance, format_type,
        and compare_direction.
        Returns a dict with an "error" key for invalid stock types.
        """
        try:
            ratio_set: list[RatioInfo] = (
                self._ratio_resolver.get_ratio_set(stock_type)
            )
        except ValueError as exc:
            return {"error": str(exc)}

        ratios: list[dict[str, str]] = [
            {
                "name": ratio.name,
                "optimal": ratio.optimal,
                "importance": ratio.importance,
                "format_type": ratio.format_type,
                "compare_direction": ratio.compare_direction,
            }
            for ratio in ratio_set
        ]

        return {
            "stock_type": stock_type,
            "ratios": ratios,
        }

    @mcp_prompt(
        name="screen_stock",
        description=(
            "Prompt template for screening one or more stocks "
            "with formatted table output."
        ),
    )
    def screen_stock(self, ticker: str, stock_type: str) -> str:
        """Prompt template for screening stocks.

        Args:
            ticker: One or more stock ticker symbols, comma-separated
                    (e.g. AAPL or AAPL,MSFT,GOOG).
            stock_type: Comma-separated stock types: div, growth, value.

        Returns a prompt string instructing the LLM to call the
        stock_screener tool for each ticker and render per-ticker
        results matching the CLI output format.
        """
        tickers: list[str] = [
            t.strip().upper() for t in ticker.split(",") if t.strip()
        ]

        if len(tickers) == 1:
            return self._build_single_ticker_prompt(
                tickers[0], stock_type
            )

        return self._build_multi_ticker_prompt(tickers, stock_type)

    @staticmethod
    def _build_single_ticker_prompt(
        ticker: str,
        stock_type: str,
    ) -> str:
        """Build the prompt string for a single ticker."""
        return (
            f"Screen the stock {ticker} for type(s): {stock_type}.\n\n"
            f"Call the stock_screener tool with ticker='{ticker}' and "
            f"stock_type='{stock_type}'.\n\n"
            f"Render the results in this exact order:\n"
            f"1. A banner header showing: {ticker}  $<price>  "
            f"(<stock_types>) where stock_types are comma-separated.\n"
            f"2. For each stock type, show:\n"
            f"   - A label line: <stock_type>: <score> / <max_score>\n"
            f"   - A markdown table with columns: Ratio, Optimal Value, "
            f"Industry Average, Real-Time Value, Importance\n"
            f"3. End with: Investment Score: <total_score> / <total_max> "
            f"(<percentage>%)\n"
        )

    @staticmethod
    def _build_multi_ticker_prompt(
        tickers: list[str],
        stock_type: str,
    ) -> str:
        """Build the prompt string for multiple tickers using few-shot examples."""
        ticker_list: str = ", ".join(tickers)
        tool_calls: str = "\n".join(
            f"   - stock_screener(ticker='{t}', stock_type='{stock_type}')"
            for t in tickers
        )

        few_shot_examples: str = (
            "## Example Output Format\n\n"
            "Below are two examples showing the EXACT format expected. "
            "Notice that each stock type has its OWN separate table with "
            "its own header row.\n\n"
            "### Example 1: NVDA\n\n"
            "NVDA  $192.53  (growth, value)\n\n"
            "Growth: 6 / 6\n\n"
            "| Ratio | Optimal Value | Industry Average | Real-Time Value "
            "| Importance |\n"
            "|-------|---------------|------------------|-----------------|"
            "------------|\n"
            "| Gross Margin | >=40% | 52% | 74.15% ✅ "
            "| % of revenue left after production costs. |\n"
            "| Operating Margin | >=15% | 22% | 64.02% ✅ "
            "| Profit from core business before taxes. |\n"
            "| EPS YoY | >=15% annually | 18% | 87.39% ✅ "
            "| Shows how fast profits are growing. |\n"
            "| Revenue Growth YoY | >=15% | 14% | 70.68% ✅ "
            "| Shows top-line revenue expansion year over year. |\n"
            "| Revenue Growth 3-5 Year CAGR | >=10% | 12% "
            "| 100.05% / 66.90% ✅ "
            "| Average revenue growth over the past 3-5 years. |\n"
            "| FCF Margin | >=10% | 16% | 46.97% ✅ "
            "| Measures how much revenue turns into cash. |\n\n"
            "Value: 5 / 10\n\n"
            "| Ratio | Optimal Value | Industry Average | Real-Time Value "
            "| Importance |\n"
            "|-------|---------------|------------------|-----------------|"
            "------------|\n"
            "| Beta | <1.0 low risk, >1.0 volatile | 1.3 | 2.21 ❌ "
            "| Measures volatility vs overall market. |\n"
            "| Forward P/E | <industry avg, >=10-20 stability | 22.0 "
            "| 15.40 ✅ "
            "| Shows if the stock is cheap or expensive based on future "
            "earnings. |\n"
            "| PEG | <1.0 | 1.8 | 0.34 ✅ "
            "| PEG <1.0 suggests undervalued relative to growth "
            "prospects. |\n"
            "| EV/EBITDA | <10 signals undervaluation | 18.0 | 27.74 ❌ "
            "| Compares total company value to operating cash "
            "earnings. |\n"
            "| P/S | <2.0, <1.0 cheap | 7.5 | 18.38 ❌ "
            "| Compares price to annual revenue. |\n"
            "| EV/Revenue | <5.0, <3.0 cheap | 8.0 | 18.11 ❌ "
            "| Measures how expensive the company is relative to its "
            "revenue. |\n"
            "| Earnings Yield | >=5% | 4.5% | 3.39% ❌ "
            "| Measures how much earnings you get for the stock price "
            "paid. |\n"
            "| Debt/EQ | <1.0 for value stocks | 0.4 | 0.07 ✅ "
            "| Shows reliance on debt vs own capital. |\n"
            "| LT Debt/EQ | <1.0 most sectors, <0.5 stable for dividend "
            "stocks | 0.2 | 0.06 ✅ "
            "| Indicates financial stability and how safely dividends can "
            "be maintained. |\n"
            "| Current Ratio | >1.5 comfortable, <1.0 liquidity issues "
            "| 2.5 | 3.44 ✅ "
            "| Ability to cover ST liabilities with ST assets. |\n\n"
            "Investment Score: 11 / 16 (68.8%)\n\n"
            "---\n\n"
            "### Example 2: NFLX\n\n"
            "NFLX  $73.81  (growth, value)\n\n"
            "Growth: 6 / 6\n\n"
            "| Ratio | Optimal Value | Industry Average | Real-Time Value "
            "| Importance |\n"
            "|-------|---------------|------------------|-----------------|"
            "------------|\n"
            "| Gross Margin | >=40% | 42% | 49.44% ✅ "
            "| % of revenue left after production costs. |\n"
            "| Operating Margin | >=15% | 12% | 30.30% ✅ "
            "| Profit from core business before taxes. |\n"
            "| EPS YoY | >=15% annually | 9% | 40.83% ✅ "
            "| Shows how fast profits are growing. |\n"
            "| Revenue Growth YoY | >=15% | 8% | 18.57% ✅ "
            "| Shows top-line revenue expansion year over year. |\n"
            "| Revenue Growth 3-5 Year CAGR | >=10% | 10% "
            "| 12.72% 12.61% ✅ "
            "| Average revenue growth over the past 3-5 years. |\n"
            "| FCF Margin | >=10% | 9% | 25.14% ✅ "
            "| Measures how much revenue turns into cash. |\n\n"
            "Value: 7 / 10\n\n"
            "| Ratio | Optimal Value | Industry Average | Real-Time Value "
            "| Importance |\n"
            "|-------|---------------|------------------|-----------------|"
            "------------|\n"
            "| Beta | <1.0 low risk, >1.0 volatile | 1.2 | 1.53 ❌ "
            "| Measures volatility vs overall market. |\n"
            "| Forward P/E | <industry avg, >=10-20 stability | 25.0 "
            "| 19.25 ✅ "
            "| Shows if the stock is cheap or expensive based on future "
            "earnings. |\n"
            "| PEG | <1.0 | 1.8 | 0.88 ✅ "
            "| PEG <1.0 suggests undervalued relative to growth "
            "prospects. |\n"
            "| EV/EBITDA | <10 signals undervaluation | 14.0 | 10.01 ✅ "
            "| Compares total company value to operating cash "
            "earnings. |\n"
            "| P/S | <2.0, <1.0 cheap | 3.5 | 6.57 ❌ "
            "| Compares price to annual revenue. |\n"
            "| EV/Revenue | <5.0, <3.0 cheap | 4.0 | 6.67 ❌ "
            "| Measures how expensive the company is relative to its "
            "revenue. |\n"
            "| Earnings Yield | >=5% | 4% | 4.19% ✅ "
            "| Measures how much earnings you get for the stock price "
            "paid. |\n"
            "| Debt/EQ | <1.0 for value stocks | 0.9 | 0.54 ✅ "
            "| Shows reliance on debt vs own capital. |\n"
            "| LT Debt/EQ | <1.0 most sectors, <0.5 stable for dividend "
            "stocks | 0.7 | 0.49 ✅ "
            "| Indicates financial stability and how safely dividends can "
            "be maintained. |\n"
            "| Current Ratio | >1.5 comfortable, <1.0 liquidity issues "
            "| 1.1 | 1.41 ✅ "
            "| Ability to cover ST liabilities with ST assets. |\n\n"
            "Investment Score: 13 / 16 (81.2%)\n\n"
            "---\n\n"
        )

        return (
            f"Screen the following stocks for type(s): {stock_type}.\n"
            f"Tickers: {ticker_list}\n\n"
            f"Call the stock_screener tool once for EACH ticker "
            f"(all calls can be made in parallel):\n"
            f"{tool_calls}\n\n"
            f"{few_shot_examples}"
            f"## Instructions\n\n"
            f"Render the results for EACH ticker following the EXACT "
            f"format shown in the examples above. Key rules:\n"
            f"- Each stock type MUST have its own SEPARATE table with "
            f"its own header row.\n"
            f"- Do NOT combine ratios from different stock types into a "
            f"single table.\n"
            f"- The Investment Score line comes AFTER all tables for that "
            f"ticker.\n"
            f"- Separate each ticker's output with a horizontal rule "
            f"(---).\n"
        )


mcp: FastMCP = FastMCP("stock-screener")
_server: StockScreenerMcpServer = StockScreenerMcpServer()
_server.register_all(mcp)


if __name__ == "__main__":
    mcp.run()
