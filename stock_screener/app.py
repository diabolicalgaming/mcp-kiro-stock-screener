"""Main application orchestrator for the Stock Screener CLI."""

from __future__ import annotations

import pandas as pd

from rich.console import Console

from stock_screener.cache import IndustryAverageCache
from stock_screener.cli import ArgumentParser
from stock_screener.industry import IndustryAverageProvider
from stock_screener.parser import HtmlParser
from stock_screener.ratios import RatioInfo
from stock_screener.ratios import RatioConfigResolver
from stock_screener.renderer import TableRenderer
from stock_screener.scorer import Scorer
from stock_screener.scraper import ScrapeError
from stock_screener.scraper import FinvizScraper


class StockScreenerApp:  # pylint: disable=too-few-public-methods
    """Main application class that orchestrates the stock screening pipeline."""

    def __init__(self) -> None:
        self._ratio_resolver: RatioConfigResolver = RatioConfigResolver()
        self._scraper: FinvizScraper = FinvizScraper()
        self._renderer: TableRenderer = TableRenderer()
        self._scorer: Scorer = Scorer()
        self._console: Console = Console()

    def run(self, argv: list[str] | None = None) -> int:
        """
        Run the stock screener pipeline.

        Returns exit code (0 success, 1 error).

        Pipeline:
        1. Parse CLI args (ticker, stock_types, api_key, no_cache, refresh)
        2. Fetch finviz page ONCE for the ticker
        3. Parse HTML for price, sector, industry (once)
        4. Render banner header ONCE with all stock types
        5. Initialize total_score = 0, total_max = 0
        6. For each stock_type in stock_types:
           a. Resolve ratio set for this type
           b. Parse ratios from cached HTML for this type's ratio set
           c. Check cache for industry averages (unless --no-cache or --refresh)
           d. On cache miss: fetch via OpenAI API, write to cache (unless --no-cache)
           e. Compute score via Scorer.score_ratios()
           f. Accumulate total_score and total_max
           g. Build DataFrame for this type
           h. Render stock type label with score
           i. Render ratio table
        7. Render Investment Score banner with cumulative totals
        """
        try:
            ticker, stock_types, api_key, no_cache, refresh = (
                ArgumentParser(argv).parse()
            )
        except SystemExit:
            return 1

        try:
            html: str = self._scraper.fetch_page(ticker)
        except ScrapeError as exc:
            self._console.print(f"[red]Error: {exc.message}[/red]")
            return 1

        try:
            parser: HtmlParser = HtmlParser(html)
            price: str = parser.parse_price()
            sector: str
            industry: str
            sector, industry = parser.parse_sector_industry()
        except (AttributeError, IndexError, TypeError) as exc:
            self._console.print(f"[red]Error parsing HTML: {exc}[/red]")
            return 1

        self._renderer.render_header(ticker, price, stock_types)

        provider: IndustryAverageProvider = IndustryAverageProvider(api_key)
        cache: IndustryAverageCache = IndustryAverageCache()
        use_cache: bool = not no_cache

        total_score: int = 0
        total_max: int = 0

        for stock_type in stock_types:
            result: tuple[int, int] | None = self._process_stock_type(
                stock_type, ticker, parser, provider, cache,
                use_cache, refresh, sector, industry,
            )
            if result is None:
                return 1
            total_score += result[0]
            total_max += result[1]

        self._renderer.render_score_banner(total_score, total_max)

        return 0

    def _process_stock_type(
        self,
        stock_type: str,
        ticker: str,
        parser: HtmlParser,
        provider: IndustryAverageProvider,
        cache: IndustryAverageCache,
        use_cache: bool,
        refresh: bool,
        sector: str,
        industry: str,
    ) -> tuple[int, int] | None:
        """
        Process a single stock type: resolve ratios, fetch industry
        averages, score, and render.

        Returns (score, max_score) on success, or None on fatal error.
        """
        try:
            ratio_set: list[RatioInfo] = (
                self._ratio_resolver.get_ratio_set(stock_type)
            )
        except ValueError as exc:
            self._console.print(f"[red]Error: {exc}[/red]")
            return None

        values: dict[str, str] = parser.parse_ratios(ratio_set)

        industry_averages: dict[str, str] | None = None

        if use_cache and not refresh:
            industry_averages = cache.get(ticker, stock_type)
            if industry_averages is not None:
                self._console.print(
                    "[dim]Using cached industry averages.[/dim]"
                )

        if industry_averages is None:
            try:
                industry_averages = provider.fetch_averages(
                    ticker, stock_type, ratio_set, sector, industry
                )
                if use_cache:
                    cache.put(ticker, stock_type, industry_averages)
            except (
                OSError, ValueError, TypeError, KeyError, RuntimeError,
            ) as exc:
                self._console.print(
                    f"[yellow]Warning: Could not fetch industry "
                    f"averages for {stock_type} — {exc}[/yellow]"
                )
                industry_averages = {r.name: "N/A" for r in ratio_set}

        dataframe: pd.DataFrame = self._renderer.build_dataframe(
            ratio_set, values, industry_averages
        )
        score: int
        max_score: int
        score, max_score = self._scorer.score_ratios(
            ratio_set, values, industry_averages, stock_type
        )
        self._renderer.render_stock_type_label(
            stock_type, score, max_score
        )
        self._renderer.render_table(dataframe)

        return score, max_score
