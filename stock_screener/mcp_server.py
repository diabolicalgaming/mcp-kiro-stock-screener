"""MCP server interface for the Stock Screener application."""

from __future__ import annotations

import os

from fastmcp import FastMCP

from stock_screener.cache import IndustryAverageCache
from stock_screener.industry import IndustryAverageProvider
from stock_screener.parser import HtmlParser
from stock_screener.ratios import RatioInfo
from stock_screener.ratios import RatioConfigResolver
from stock_screener.scorer import Scorer
from stock_screener.scraper import ScrapeError
from stock_screener.scraper import FinvizScraper


mcp: FastMCP = FastMCP("stock-screener")

VALID_STOCK_TYPES: list[str] = ["div", "growth", "value"]


def _parse_stock_types(raw: str) -> list[str]:
    """
    Split comma-separated stock types, deduplicate, and validate.

    Returns a list of unique, validated stock type strings.
    Raises ValueError if any type is invalid.
    """
    parts: list[str] = [part.strip() for part in raw.split(",")]
    unique: list[str] = list(dict.fromkeys(parts))

    for stock_type in unique:
        if stock_type not in VALID_STOCK_TYPES:
            raise ValueError(
                f"Unknown stock type '{stock_type}'. "
                f"Valid types: {VALID_STOCK_TYPES}"
            )

    return unique


def _resolve_api_key(api_key: str) -> str | None:
    """Return the API key from the parameter or environment variable."""
    if api_key:
        return api_key
    return os.environ.get("OPENAI_API_KEY")


def _process_stock_type(
    stock_type: str,
    parser: HtmlParser,
    ratio_resolver: RatioConfigResolver,
    scorer: Scorer,
    provider: IndustryAverageProvider,
    cache: IndustryAverageCache,
    use_cache: bool,
    refresh: bool,
    ticker: str,
    sector: str,
    industry: str,
) -> dict:
    """
    Process a single stock type and return a structured dict.

    Returns a dict with type, score, max_score, and ratios list.
    """
    ratio_set: list[RatioInfo] = ratio_resolver.get_ratio_set(stock_type)
    values: dict[str, str] = parser.parse_ratios(ratio_set)

    industry_averages: dict[str, str] | None = None

    if use_cache and not refresh:
        industry_averages = cache.get(ticker, stock_type)

    if industry_averages is None:
        try:
            industry_averages = provider.fetch_averages(
                ticker, stock_type, ratio_set, sector, industry
            )
            if use_cache:
                cache.put(ticker, stock_type, industry_averages)
        except (
            OSError, ValueError, TypeError, KeyError, RuntimeError,
        ):
            industry_averages = {r.name: "N/A" for r in ratio_set}

    score: int
    max_score: int
    score, max_score = scorer.score_ratios(
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


@mcp.tool
def stock_screener(  # pylint: disable=too-many-return-statements
    ticker: str,
    stock_type: str,
    api_key: str = "",
    no_cache: bool = False,
    refresh: bool = False,
) -> dict:
    """
    Screen a stock by ticker and type(s).

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
    if no_cache and refresh:
        return {
            "error": (
                "The 'no_cache' and 'refresh' options are mutually "
                "exclusive. Provide only one."
            )
        }

    resolved_key: str | None = _resolve_api_key(api_key)
    if resolved_key is None:
        return {
            "error": (
                "No API key provided. Pass 'api_key' or set the "
                "OPENAI_API_KEY environment variable."
            )
        }

    try:
        stock_types: list[str] = _parse_stock_types(stock_type)
    except ValueError as exc:
        return {"error": str(exc)}

    normalized_ticker: str = ticker.upper()

    scraper: FinvizScraper = FinvizScraper()
    try:
        html: str = scraper.fetch_page(normalized_ticker)
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

    ratio_resolver: RatioConfigResolver = RatioConfigResolver()
    scorer: Scorer = Scorer()
    provider: IndustryAverageProvider = IndustryAverageProvider(resolved_key)
    cache: IndustryAverageCache = IndustryAverageCache()
    use_cache: bool = not no_cache

    total_score: int = 0
    total_max: int = 0
    type_results: list[dict] = []

    for st in stock_types:
        try:
            result: dict = _process_stock_type(
                st, parser, ratio_resolver, scorer, provider,
                cache, use_cache, refresh, normalized_ticker,
                sector, industry_name,
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


@mcp.tool
def get_ratio_definitions(stock_type: str) -> dict:
    """
    Get the ratio definitions for a stock type.

    Args:
        stock_type: One of: div, growth, value.

    Returns a dict with the stock_type and a list of ratio definitions,
    each containing name, optimal, importance, format_type, and compare_direction.
    Returns a dict with an "error" key for invalid stock types.
    """
    resolver: RatioConfigResolver = RatioConfigResolver()
    try:
        ratio_set: list[RatioInfo] = resolver.get_ratio_set(stock_type)
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


@mcp.prompt
def screen_stock(ticker: str, stock_type: str) -> str:
    """
    Prompt template for screening a stock with formatted table output.

    Args:
        ticker: Stock ticker symbol (e.g. AAPL, MSFT).
        stock_type: Comma-separated stock types: div, growth, value.

    Returns a prompt string instructing the LLM to call the stock_screener
    tool and render the results matching the CLI output format.
    """
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


if __name__ == "__main__":
    mcp.run()
