# Implementation Plan: Stock Screener CLI

## Overview

A Python CLI stock screener that accepts a ticker symbol and one or more comma-separated stock types (div, growth, value). It scrapes financial ratios from finviz.com using Selenium, parses HTML with BeautifulSoup, and retrieves sector/industry-aware industry averages via the OpenAI API. Industry averages are cached locally at `~/.stock_screener/cache.json` with a 7-day TTL, controllable via `--no-cache` and `--refresh` flags. An investment scoring system compares real-time values against industry averages per ratio, with dividend ratios requiring an additional optimal-range gate. Results are loaded into Pandas DataFrames and rendered as styled terminal tables via tabulate and Rich, with per-type score labels and a cumulative Investment Score banner. The application is also exposed as an MCP server via FastMCP, providing `stock_screener` and `get_ratio_definitions` tools that return structured JSON data for LLM client consumption. Full OOP, strict typing, PEP 8, snake_case throughout. No tests per coding standards.

## Notes

- No tests are included per project coding standards: "No testing required because this is a lightweight application."
- All modules use strict typing, OOP, snake_case, and PEP 8 formatting.
- Imports grouped by library and ordered by line length within each group.
- All I/O and network operations wrapped in try-except blocks.
- Tasks 10-15 cover the industry-average column feature (Requirements 8-12).
- Tasks 16-19 cover the local file-based caching feature (Requirements 13-14).
- The `openai` package must be installed before implementing task 11.
- The cache TTL defaults to 7 days and can be changed by updating `DEFAULT_TTL_DAYS` in `stock_screener/cache.py`.
- Tasks 20-23 cover the sector/industry prompt enhancement (Requirement 15) that fixes N/A responses for growth ratios.
- Tasks 24-27 cover multi-stock-type support (Requirements 16-23).
- The format-aware industry average prompt fix is merged into Task 2 (`format_type` field on `RatioInfo`) and Task 21 (format-aware `_build_prompt` + stale cache clearing).
- Tasks 28-29 cover the investment scoring system feature including compound finviz value parsing and dual-gate dividend scoring. Task 2.2 adds `compare_direction` to `RatioInfo`, Task 28 updates the `Scorer` class, Tasks 25.2-25.3 update the renderer for score display, and Task 26.4 integrates scoring into the app pipeline.
- Tasks 30-32 cover the MCP server interface (Requirement 24). Task 30 creates `mcp_server.py` with two tools (`stock_screener` and `get_ratio_definitions`), Task 31 registers the server in workspace-level `.kiro/settings/mcp.json`, and Task 32 is the verification checkpoint. The `fastmcp` package must be installed before implementing Task 30.

## Tasks

- [x] 1. Set up project structure and package
  - [x] 1.1 Create the `stock_screener/` package directory with `__init__.py`
    - Create `stock_screener/__init__.py` as an empty init file
    - Create `main.py` entry point stub that imports and runs `StockScreenerApp`
    - _Requirements: 1.1_

- [x] 2. Implement ratio data model and configuration
  - [x] 2.1 Create `stock_screener/ratios.py` with `RatioInfo` dataclass and `RatioConfigResolver` class
    - Define frozen `RatioInfo` dataclass with fields: `name`, `finviz_label`, `optimal`, `importance`, `format_type`
    - `format_type` is a `str` field with valid values `"percentage"` or `"multiple"` — indicates how the ratio's industry average value should be formatted
    - Implement `RatioConfigResolver` with `_RATIO_SETS` class-level dict mapping stock types to `list[RatioInfo]`
    - Populate all three ratio sets: "div" (3 ratios, all `format_type="percentage"`), "growth" (6 ratios, all `format_type="percentage"`), "value" (10 ratios, all `format_type="multiple"`)
    - Implement `get_ratio_set()` method that raises `ValueError` for unknown stock types
    - Use strict typing on all parameters and return types
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3_
  - [x] 2.2 Add `compare_direction` field to `RatioInfo` dataclass in `stock_screener/ratios.py`
    - Add `compare_direction: str` as the sixth field on the frozen `RatioInfo` dataclass, after `format_type`
    - Valid values: `"higher_is_better"` or `"lower_is_better"`
    - Update every `RatioInfo` instance in `_RATIO_SETS` to include the `compare_direction` argument:
      - `"higher_is_better"`: Dividend Yield, Dividend Payout, Dividend Growth Rate (3-5 yr), Gross Margin, Operating Margin, EPS YoY, Revenue Growth YoY, Revenue Growth 3-5 Year CAGR, FCF Margin, Current Ratio
      - `"lower_is_better"`: Beta, P/E, Forward P/E, PEG, P/B, P/S, EV/EBITDA, Debt/EQ, LT Debt/EQ
    - _Requirements: 2.4 (updated), 19 (scoring system)_
  - [x] 2.3 Update `_RATIO_SETS["value"]` to new value ratio set in `stock_screener/ratios.py`
    - Remove the `P/E` RatioInfo entry (name: "P/E", finviz_label: "P/E")
    - Remove the `P/B` RatioInfo entry (name: "P/B", finviz_label: "P/B")
    - Add `EV/Revenue` RatioInfo entry: `RatioInfo("EV/Revenue", "EV/Sales", "<5.0, <3.0 cheap", "Measures how expensive the company is relative to its revenue.", "multiple", "lower_is_better")`
    - Add `Earnings Yield` RatioInfo entry: `RatioInfo("Earnings Yield", "", ">=5%", "Measures how much earnings you get for the stock price paid.", "percentage", "higher_is_better")` — note empty `finviz_label` since it is a Calculated_Ratio
    - Reorder the value list to: Beta, Forward P/E, PEG, EV/EBITDA, P/S, EV/Revenue, Earnings Yield, Debt/EQ, LT Debt/EQ, Current Ratio
    - Ensure the total count remains 10 ratios
    - Update `compare_direction` listings: add Earnings Yield to `"higher_is_better"`, add EV/Revenue to `"lower_is_better"`, remove P/E and P/B from `"lower_is_better"`
    - _Requirements: 2.3, 2.7, 2.8, 2.11, 3.3, 4.3_
  - [x] 2.4 Add `source_labels` and `calculation` optional fields to `RatioInfo` dataclass in `stock_screener/ratios.py`
    - Add `source_labels: list[str] = field(default_factory=list)` as an optional field on the `RatioInfo` dataclass
    - Add `calculation: str = ""` as an optional field on the `RatioInfo` dataclass
    - Update the `Earnings Yield` entry to include `source_labels=["P/E"]` and `calculation="inverse_pe_times_100"`
    - Existing ratios remain unchanged (empty defaults)
    - _Requirements: 2.8, 26.1_

- [x] 3. Implement CLI argument parsing
  - [x] 3.1 Create `stock_screener/cli.py` with `ArgumentParser` class
    - Wrap `argparse.ArgumentParser` to accept positional `ticker` and `stock_type` arguments
    - Validate `stock_type` against `VALID_STOCK_TYPES: list[str] = ["div", "growth", "value"]`
    - Normalize ticker to uppercase in `parse()` method
    - Return `tuple[str, str]` of `(ticker_uppercase, stock_type)`
    - Display usage on missing args, error on invalid stock type, exit code 1 on failure
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x] 3.2 Add ticker validation to `ArgumentParser` in `stock_screener/cli.py`
    - Add `import re` to the module imports
    - Add class-level `TICKER_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z]+(-[a-zA-Z]+)?$")` compiled regex
    - Add `_validate_ticker(value: str) -> str` static method that performs two-stage validation:
      1. **Comma check**: if `","` is in the value, raise `argparse.ArgumentTypeError` with message: `"Only one ticker is allowed. Use the MCP server for multiple tickers."`
      2. **Format check**: if the value does not match `TICKER_PATTERN`, raise `argparse.ArgumentTypeError` with message: `"Invalid ticker '{value}'. Ticker must be alphabetic, optionally with a single hyphen for share classes (e.g., BRK-B)."`
      3. Return `value.strip().upper()` on success
    - Update the `ticker` positional argument in `_build_parser()` to use `type=self._validate_ticker` instead of `type=str`
    - Update the `ticker` help text to: `"Single stock ticker symbol (e.g. AAPL, MSFT, BRK-B)."`
    - Add a belt-and-suspenders comma check in `parse()` after `args.ticker` assignment as a safety net
    - _Requirements: 1.5, 1.6, 1.7, 1.8_

- [x] 4. Implement web scraping with Selenium
  - [x] 4.1 Create `stock_screener/scraper.py` with `ScrapeError` exception and `FinvizScraper` class
    - Define `ScrapeError(Exception)` with `message: str` and `status_code: int | None` attributes
    - Implement `FinvizScraper` with headless Chrome via `_build_options()` method
    - Set browser-like User-Agent header to avoid blocks
    - Implement `fetch_page(ticker: str) -> str` that navigates to `https://finviz.com/quote.ashx?t={ticker}`
    - Wrap all Selenium exceptions in `ScrapeError` via try-except
    - Ensure WebDriver is properly quit in a finally block
    - _Requirements: 5.1, 5.4, 5.5, 7.4_

- [x] 5. Implement HTML parsing with BeautifulSoup
  - [x] 5.1 Create `stock_screener/parser.py` with `HtmlParser` class
    - Initialize `BeautifulSoup` with `html.parser` in constructor
    - Implement `parse_ratios(ratio_set: list[RatioInfo]) -> dict[str, str]` to extract ratio values by label
    - Navigate finviz snapshot table where `<td>` cells alternate between label and value
    - Return "N/A" for any ratio not found in the HTML
    - Implement `parse_price() -> str` to extract current stock price, returning "N/A" if not found
    - Preserve special characters (%, -) as-is in extracted values
    - After extracting the value for the "Sales past 3/5Y" label, check if it matches the pattern `r"(-?[\d.]+%)(-?[\d.]+%)"` (two concatenated percentage values). If matched, reformat to `"{group1} / {group2}"` (e.g., "41.55%51.61%" → "41.55% / 51.61%"). If not matched (single value), store unchanged.
    - Wrap all parsing in try-except for graceful degradation
    - _Requirements: 5.2, 5.3, 5.6, 7.1, 7.2, 7.3, 27.1, 27.2, 27.4, 27.5_
  - [x] 5.2 Implement generic Calculated_Ratio support in `stock_screener/parser.py`
    - In `parse_ratios()`, for each ratio in the ratio_set:
      - If `ratio.finviz_label` is non-empty: look up the value directly from the HTML (existing behavior)
      - If `ratio.finviz_label` is empty AND `ratio.calculation` is non-empty: treat as a Calculated_Ratio
        - Extract the numeric values for each label in `ratio.source_labels` from the HTML
        - Dispatch to a calculation function based on `ratio.calculation` using a `_CALCULATIONS` dict
        - Format and store the result as a percentage string (e.g., `"3.29%"`)
        - If any source value is missing, non-numeric, zero, or negative (where division is involved): store `"N/A"`
    - Define a class-level or module-level `_CALCULATIONS` dispatch dict mapping calculation identifiers to callables:
      - `"inverse_pe_times_100"`: `lambda vals: (1 / vals[0]) * 100 if vals[0] > 0 else None`
      - `"ps_div_pfcf_times_100"`: `lambda vals: (vals[0] / vals[1]) * 100 if vals[1] > 0 else None`
    - This approach is generic — adding future calculated ratios requires only a new `RatioInfo` entry and a new calculation function, no parser changes
    - Wrap all calculations in a try-except block for safety
    - _Requirements: 2.8, 2.9, 2.10, 26.1, 26.3, 26.4, 26.5, 26.6_

- [x] 6. Checkpoint - Verify core data pipeline
  - Ensure all modules created so far are syntactically correct and importable, ask the user if questions arise.

- [x] 7. Implement table rendering with Pandas, tabulate, and Rich
  - [x] 7.1 Create `stock_screener/renderer.py` with `TableRenderer` class
    - Initialize `Rich Console` in constructor
    - Implement `build_dataframe(ratio_set, values) -> pd.DataFrame` with columns: Ratio, Optimal Value, Real-Time Value, Importance
    - Implement `render_header(ticker, price, stock_type) -> None` using Rich markup: ticker in `[bright_blue]`, price in `[bright_green]`, stock type in default color
    - Implement `render_table(dataframe) -> None` using `tabulate(df, headers="keys", tablefmt=...)` printed via Rich console
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 8. Implement application orchestrator and entry point
  - [x] 8.1 Create `stock_screener/app.py` with `StockScreenerApp` class
    - Instantiate `RatioConfigResolver`, `FinvizScraper`, and `TableRenderer` in constructor
    - Implement `run(argv: list[str] | None = None) -> int` orchestrating the full pipeline:
      - Parse CLI args via `ArgumentParser`
      - Resolve ratio set via `RatioConfigResolver`
      - Fetch page HTML via `FinvizScraper`
      - Parse ratios and price via `HtmlParser`
      - Build DataFrame and render output via `TableRenderer`
    - Catch `ScrapeError` and `ValueError`, print styled error via Rich, return exit code 1
    - Return exit code 0 on success
    - _Requirements: 1.1, 5.1, 5.4, 5.5, 6.5_
  - [x] 8.2 Finalize `main.py` entry point
    - Import `StockScreenerApp` and call `sys.exit(app.run())` in `main()` function
    - Guard with `if __name__ == "__main__"` block
    - _Requirements: 1.1_

- [x] 9. Final checkpoint - Verify complete application
  - Ensure all modules are wired together correctly and the application runs end-to-end, ask the user if questions arise.

- [x] 10. Update CLI argument parsing for API key
  - [x] 10.1 Add `--api-key` optional argument to `ArgumentParser._build_parser()` in `stock_screener/cli.py`
    - Add `--api-key` as an optional argument with `type=str` and `default=None`
    - _Requirements: 8.1_
  - [x] 10.2 Update `ArgumentParser.parse()` to return 3-tuple `(ticker, stock_type, api_key)`
    - Read `--api-key` from parsed args first; if `None`, fall back to `os.environ.get("OPENAI_API_KEY")`
    - If neither source provides a key, print error to stderr and call `sys.exit(1)`
    - Update return type annotation to `tuple[str, str, str]`
    - Add `import os` to the file imports
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 11. Create `stock_screener/industry.py` with `IndustryAverageProvider` class
  - [x] 11.1 Create the new module `stock_screener/industry.py`
    - Import `openai`, `json`, `datetime`, `rich.console.Console`, and `stock_screener.ratios.RatioInfo`
    - Define class constant `MODEL: str = "gpt-5.4-mini"`
    - Implement `__init__(self, api_key: str)` that creates an `openai.OpenAI` client with the explicit `api_key`
    - Implement `_build_prompt(self, ticker, stock_type, ratio_set) -> str` that builds a concise, token-efficient prompt listing only the ratio names from the active ratio set, including ticker and stock type for context, and dynamically inserting the current year via `datetime.date.today().year`
    - Implement `fetch_averages(self, ticker, stock_type, ratio_set) -> dict[str, str]` that calls the OpenAI chat completions API with `response_format={"type": "json_object"}`, parses the JSON response into a dict mapping ratio name to value string, and fills `"N/A"` for any missing ratio
    - Catch `openai.RateLimitError` for 429 errors and log a descriptive "insufficient funds" message to console, returning `"N/A"` for all ratios
    - Catch all other exceptions as fallback, returning `"N/A"` for all ratios
    - Use strict typing on all parameters and return types
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10_

- [x] 12. Update `TableRenderer.build_dataframe` for five-column layout
  - [x] 12.1 Update `build_dataframe` in `stock_screener/renderer.py` to accept `industry_averages: dict[str, str]` parameter
    - Add `industry_averages` as the third parameter after `values`
    - Update the row-building list comprehension to include `"Industry Average": industry_averages.get(ratio.name, "N/A")`
    - Set column order to: Ratio, Optimal Value, Industry Average, Real-Time Value, Importance
    - Update the fallback empty DataFrame columns to match the new five-column order
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 13. Update `TableRenderer.render_table` for Industry Average column coloring
  - [x] 13.1 Update `render_table` in `stock_screener/renderer.py` to add the Industry Average column with conditional coloring
    - Add a new `table.add_column("Industry Average")` call between "Optimal Value" and "Real-Time Value"
    - In the row iteration, read the `"Industry Average"` value from each row
    - Apply the same `_realtime_style` color logic to the Industry Average cell (negative → red, within optimal → bright_green, otherwise → default, "N/A" → default)
    - Pass the styled Industry Average `Text` object in the correct position in `table.add_row()`
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 14. Integrate `IndustryAverageProvider` into `StockScreenerApp.run()`
  - [x] 14.1 Update `stock_screener/app.py` to wire in the industry-average step
    - Add `from stock_screener.industry import IndustryAverageProvider` import
    - Update the `ArgumentParser` call to unpack the 3-tuple: `ticker, stock_type, api_key = ArgumentParser(argv).parse()`
    - After HTML parsing, instantiate `IndustryAverageProvider(api_key)` and call `fetch_averages(ticker, stock_type, ratio_set)`
    - Wrap the `IndustryAverageProvider` call in a try-except that logs the error and falls back to `"N/A"` for all ratios if any unexpected exception occurs
    - Pass the `industry_averages` dict to `self._renderer.build_dataframe(ratio_set, values, industry_averages)`
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 15. Final checkpoint - Verify industry-average integration
  - Ensure all updated and new modules are syntactically correct and importable, verify the five-column DataFrame structure, and ask the user if questions arise.

- [x] 16. Implement local file-based cache for industry averages
  - [x] 16.1 Create `stock_screener/cache.py` with `IndustryAverageCache` class
    - Define class constant `DEFAULT_TTL_DAYS: int = 7` for configurable TTL
    - Store cache file at `~/.stock_screener/cache.json` via `pathlib.Path`
    - Implement `__init__(self, ttl_days: int = DEFAULT_TTL_DAYS)` that resolves the cache path and creates the directory if needed
    - Implement `_load() -> dict` to read and parse the JSON cache file, returning empty dict on any failure
    - Implement `_save(data: dict) -> None` to write the full cache dict to disk
    - Implement `_is_expired(timestamp_str: str) -> bool` to check if a cached entry exceeds the TTL
    - Implement `get(ticker: str, stock_type: str) -> dict[str, str] | None` to return cached averages or None on miss/expiry
    - Implement `put(ticker: str, stock_type: str, averages: dict[str, str]) -> None` to store averages with current ISO 8601 timestamp
    - Structure cache as `{"AAPL": {"div": {"timestamp": "...", "averages": {...}}, ...}}`
    - Wrap all file I/O in try-except — log warnings via Rich console, never crash
    - Use strict typing on all parameters and return types
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

- [x] 17. Add `--no-cache` and `--refresh` CLI flags
  - [x] 17.1 Update `ArgumentParser._build_parser()` in `stock_screener/cli.py`
    - Add `--no-cache` as a `store_true` flag with help text explaining it disables caching entirely
    - Add `--refresh` as a `store_true` flag with help text explaining it forces a fresh API call but updates the cache
    - _Requirements: 14.1, 14.2_
  - [x] 17.2 Update `ArgumentParser.parse()` to return 5-tuple
    - Update return type to `tuple[str, str, str, bool, bool]`
    - Extract `no_cache` and `refresh` from parsed args
    - Return `(ticker, stock_type, api_key, no_cache, refresh)`
    - _Requirements: 14.3, 14.4_

- [x] 18. Integrate cache into application pipeline
  - [x] 18.1 Update `stock_screener/app.py` to use `IndustryAverageCache`
    - Add `from stock_screener.cache import IndustryAverageCache` import
    - Update `ArgumentParser` call to unpack the 5-tuple: `ticker, stock_type, api_key, no_cache, refresh`
    - After HTML parsing, instantiate `IndustryAverageCache()` and determine `use_cache = not no_cache`
    - If `use_cache` and not `refresh`, attempt `cache.get(ticker, stock_type)` — on hit, print dim message and skip API call
    - On cache miss or refresh, call `IndustryAverageProvider` as before
    - On successful API fetch and `use_cache`, call `cache.put(ticker, stock_type, industry_averages)`
    - _Requirements: 13.4, 14.1, 14.2, 14.3_

- [x] 19. Final checkpoint - Verify caching integration
  - Ensure cache file is created at `~/.stock_screener/cache.json` on first run, verify cache hits on subsequent runs, verify `--no-cache` and `--refresh` flags work correctly.

- [x] 20. Add `parse_sector_industry()` method to `HtmlParser`
  - [x] 20.1 Update `stock_screener/parser.py` to extract sector and industry from finviz HTML
    - Add `parse_sector_industry(self) -> tuple[str, str]` method
    - Locate the `div` element with class `quote-links whitespace-nowrap gap-8`
    - Extract the text of the first `<a>` tag as sector and the second `<a>` tag as industry
    - Return `("Unknown", "Unknown")` if the div or `<a>` tags cannot be found
    - Wrap all parsing in try-except for graceful degradation
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 21. Update `IndustryAverageProvider` prompt to use sector/industry context and format-aware instructions
  - [x] 21.1 Update `_build_prompt()` in `stock_screener/industry.py` to accept `sector` and `industry` parameters and generate format-aware instructions
    - Add `sector: str` and `industry: str` parameters to `_build_prompt()`
    - Partition `ratio_set` into `percentage_ratios` and `multiple_ratios` based on `RatioInfo.format_type`
    - Build separate JSON templates for each non-empty group
    - For percentage ratios: instruct `"values must be non-empty percentage strings (e.g. '15%')"`
    - For multiple ratios: instruct `"values must be non-empty plain number strings without '%' (e.g. '22.0')"`
    - If one group is empty, omit its template and instruction block entirely
    - Keep the current year dynamically resolved via `datetime.date.today().year`
    - Include sector and industry context in the prompt
    - _Requirements: 15.6, 15.7, 15.9, 15.10, 9.5, 9.7_
  - [x] 21.2 Update `fetch_averages()` in `stock_screener/industry.py` to accept and pass `sector` and `industry`
    - Add `sector: str` and `industry: str` parameters to `fetch_averages()`
    - Pass them through to `_build_prompt()`
    - Update the system message to: `"Return JSON only. No explanation. Every value must be a non-empty string."`
    - _Requirements: 15.5, 15.8_
  - [x] 21.3 Clear stale cached data at `~/.stock_screener/cache.json` containing incorrect percentage-suffixed values
    - Cached "value" type entries contain incorrect `%`-suffixed values from the old prompt
    - After clearing, the next run will re-fetch with the corrected prompt
    - _Requirements: 13.4_

- [x] 22. Wire sector/industry extraction into application pipeline
  - [x] 22.1 Update `stock_screener/app.py` to extract and pass sector/industry
    - After HTML parsing, call `parser.parse_sector_industry()` to get `(sector, industry)`
    - Pass `sector` and `industry` to `provider.fetch_averages(ticker, stock_type, ratio_set, sector, industry)`
    - _Requirements: 15.5, 12.2_

- [x] 23. Final checkpoint - Verify sector/industry prompt enhancement
  - Verify that all three stock types (div, growth, value) return non-N/A industry averages for AAPL and at least one other ticker.

- [x] 24. Update ArgumentParser for comma-separated stock types
  - [x] 24.1 Add `_parse_stock_types(self, raw: str) -> list[str]` method to `stock_screener/cli.py`
    - Split the raw string on commas via `raw.split(",")`
    - Strip whitespace from each element
    - Deduplicate preserving first-occurrence order using `dict.fromkeys()` pattern
    - Validate each type against `VALID_STOCK_TYPES` — print error identifying the invalid type and `sys.exit(1)` on failure
    - Return the validated `list[str]`
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_
  - [x] 24.2 Update `parse()` return type and logic in `stock_screener/cli.py`
    - Change return type from `tuple[str, str, str, bool, bool]` to `tuple[str, list[str], str, bool, bool]`
    - Replace inline `stock_type` validation with a call to `self._parse_stock_types(args.stock_type)`
    - Return `(ticker, stock_types, api_key, no_cache, refresh)` where `stock_types` is `list[str]`
    - A single stock type without a comma produces a one-element list
    - _Requirements: 23.1, 23.2, 16.5_
  - [x] 24.3 Update help text for the `stock_type` positional argument in `_build_parser()`
    - Change help string to indicate comma-separated values are accepted (e.g., `"Stock type(s): div, growth, value (comma-separated for multiple)"`)
    - _Requirements: 16.1_

- [x] 25. Update TableRenderer for multi-stock-type support
  - [x] 25.1 Update `render_header()` signature and logic in `stock_screener/renderer.py`
    - Change parameter from `stock_type: str` to `stock_types: list[str]`
    - Join stock types with `", "` for display in the banner parentheses
    - Single type renders as `(div)`, multiple as `(growth, value)`
    - _Requirements: 18.1, 18.2, 18.3_
  - [x] 25.2 Update `render_stock_type_label()` in `stock_screener/renderer.py` to include score display
    - Change signature from `render_stock_type_label(self, stock_type: str)` to `render_stock_type_label(self, stock_type: str, score: int, max_score: int)`
    - Build a Rich `Text` object with the format `{stock_type}: {score} / {max_score}`
    - Apply styles: `stock_type` in `[cyan]`, `score` and `max_score` in `[bright_magenta]`, `:` and `/` in white (default)
    - Print the styled text followed by a blank line via `self._console.print()`
    - _Requirements: 19.2 (updated for scoring display)_
  - [x] 25.3 Add `render_score_banner(self, total_score: int, total_max: int) -> None` method to `stock_screener/renderer.py`
    - Compute percentage: `(total_score / total_max * 100.0)` if `total_max > 0`, else `0.0`
    - Determine percentage color: `green` if percentage > 70, `yellow` if 50 ≤ percentage ≤ 70, `red` if percentage < 50
    - Build a Rich `Text` object with format `Investment Score: {total_score} / {total_max} ({percentage:.1f}%)`
    - Apply `bright_magenta` style to `total_score` and `total_max` numbers, percentage color to the percentage value
    - Wrap in a `Rich Panel` with `border_style="bright_blue"` and `expand=True`
    - Print via `self._console.print()`
    - _Requirements: 19 (Investment Score banner)_

- [x] 26. Restructure StockScreenerApp.run() for multi-stock-type loop
  - [x] 26.1 Update CLI unpacking in `stock_screener/app.py`
    - Change `ticker, stock_type, api_key, no_cache, refresh` to `ticker, stock_types, api_key, no_cache, refresh`
    - _Requirements: 23.1_
  - [x] 26.2 Keep single HTML fetch and single parse for price/sector/industry
    - `FinvizScraper.fetch_page(ticker)` called once before the loop
    - `HtmlParser` instantiated once; `parse_price()` and `parse_sector_industry()` called once
    - _Requirements: 17.1, 17.2_
  - [x] 26.3 Render banner header once with all stock types
    - Call `self._renderer.render_header(ticker, price, stock_types)` once before the loop, passing the full `list[str]`
    - _Requirements: 18.1, 18.2_
  - [x] 26.4 Integrate scoring into per-stock-type processing loop
    - Add `from stock_screener.scorer import Scorer` import to `stock_screener/app.py`
    - Instantiate `Scorer` in `StockScreenerApp.__init__()` as `self._scorer: Scorer = Scorer()`
    - Initialize `total_score: int = 0` and `total_max: int = 0` before the stock-type loop
    - Instantiate `IndustryAverageProvider` and `IndustryAverageCache` once before the loop, reuse across iterations
    - For each `stock_type` in `stock_types`:
      - Resolve ratio set via `RatioConfigResolver.get_ratio_set(stock_type)`
      - Parse ratios from cached HTML via `HtmlParser.parse_ratios(ratio_set)`
      - Check cache via `IndustryAverageCache.get(ticker, stock_type)` unless `--no-cache` or `--refresh`
      - On cache miss: fetch via `IndustryAverageProvider.fetch_averages(...)`, write to cache unless `--no-cache`
      - Compute score: `score, max_score = self._scorer.score_ratios(ratio_set, values, industry_averages, stock_type)`
      - Accumulate: `total_score += score` and `total_max += max_score`
      - Build DataFrame via `TableRenderer.build_dataframe(ratio_set, values, industry_averages)`
      - Render stock type label with score via `TableRenderer.render_stock_type_label(stock_type, score, max_score)`
      - Render table via `TableRenderer.render_table(dataframe)`
    - After the loop: call `self._renderer.render_score_banner(total_score, total_max)`
    - _Requirements: 19.1, 19.2, 19.3, 20.1, 20.2, 20.3, 21.1, 21.2, 21.3, 21.4, 22.1, 22.2, 19 (scoring integration)_
  - [x] 26.5 Add error isolation for per-type IndustryAverageProvider failures
    - If `IndustryAverageProvider` fails for one stock type, log the error, use `"N/A"` fallback values for that type, and continue processing remaining stock types
    - A `ValueError` from `RatioConfigResolver` for an invalid type should still exit with code 1 (configuration error)
    - _Requirements: 22.3_

- [x] 27. Checkpoint - Verify multi-stock-type support works end-to-end
  - Ensure all updated modules are syntactically correct and importable
  - Verify single stock type still works as before (backward compatibility)
  - Verify comma-separated stock types produce one banner header and multiple ratio tables
  - Verify `--no-cache` and `--refresh` flags apply uniformly to all stock types
  - Ask the user if questions arise.

- [x] 28. Update `stock_screener/scorer.py` — `Scorer` class
  - [x] 28.1 Update `_parse_numeric` in `stock_screener/scorer.py` to handle compound finviz values
    - Add `import re` to the module imports
    - Replace the current strip-and-float logic with `re.findall(r"-?[\d.]+", stripped)` to extract all numeric tokens
    - Take the last token (`tokens[-1]`) and convert to `float`
    - Return `None` for `"N/A"`, `"-"`, empty strings, no tokens found, or any `ValueError` during `float()` conversion
    - This handles compound finviz formats: `"4.23 (2.91%)"` → `2.91`, `"5.04% 6.13%"` → `6.13`, `"62.63%"` → `62.63`
    - Growth and value ratios are unaffected since they return single-value strings from finviz
    - _Requirements: 5.4, 19 (scoring system)_
  - [x] 28.2 Update `score_ratios` in `stock_screener/scorer.py` to implement dual-gate scoring for dividend ratios
    - Add `stock_type: str = ""` as an optional parameter to `score_ratios()`
    - For growth and value stock types: scoring logic remains unchanged (beat industry average only)
    - For dividend stock type (`stock_type == "div"`): a ratio scores a point only when BOTH conditions are met:
      (a) the real-time value beats the industry average based on `compare_direction`, AND
      (b) the real-time value falls within the optimal value range defined by `RatioInfo.optimal`
    - Reuse the optimal range parsing logic from `TableRenderer._parse_optimal` / `_OptimalRange.is_within`
    - _Requirements: 5.4, 19 (scoring rules)_
  - [x] 28.3 Update `score_ratios` in `stock_screener/scorer.py` to split on ` / ` for Revenue Growth 3-5 Year CAGR scoring
    - Change the condition from `"/" in raw_realtime` to `" / " in raw_realtime` for the "Revenue Growth 3-5 Year CAGR" special case
    - Split on `" / "` (space-slash-space) and take the first segment (the 3-year CAGR)
    - Pass the first segment to `_parse_numeric()` for scoring
    - _Requirements: 27.3_

- [x] 29. Checkpoint - Verify scoring system with compound value parsing and dual-gate dividend scoring
  - Ensure `stock_screener/scorer.py` is syntactically correct and importable
  - Ensure `_parse_numeric` correctly extracts the last numeric token from compound finviz values
  - Ensure dividend scoring requires both beating the industry average and falling within the optimal range
  - Ensure growth and value scoring remains unchanged (beat industry average only)
  - Ensure `render_stock_type_label` displays score in the format `{stock_type}: {score} / {max}` with correct colors
  - Ensure `render_score_banner` displays the cumulative Investment Score panel with correct color thresholds
  - Ensure the scoring pipeline is integrated into `StockScreenerApp.run()` with score accumulation and `stock_type` passed to `score_ratios`
  - Run mypy and pylint to verify no type or lint errors
  - Ask the user if questions arise.

- [x] 30. Create MCP server module with FastMCP
  - [x] 30.1 Create `stock_screener/mcp_server.py` with FastMCP server instance and `get_ratio_definitions` tool
    - Import `FastMCP` from `fastmcp`
    - Create module-level `mcp: FastMCP = FastMCP("stock-screener")` instance
    - Import `RatioConfigResolver` and `RatioInfo` from `stock_screener.ratios`
    - Implement `get_ratio_definitions(stock_type: str) -> dict` tool decorated with `@mcp.tool`
    - On valid stock type: return `{"stock_type": ..., "ratios": [...]}` where each ratio is a dict with `name`, `optimal`, `importance`, `format_type`, `compare_direction`
    - On invalid stock type (`ValueError` from `RatioConfigResolver`): return `{"error": "..."}` with descriptive message
    - Add `if __name__ == "__main__": mcp.run()` entry point block
    - Use strict typing on all parameters and return types
    - _Requirements: 24.1, 24.2, 24.4, 24.8, 24.11, 24.12_
  - [x] 30.2 Implement `stock_screener` tool in `stock_screener/mcp_server.py`
    - Import `FinvizScraper`, `ScrapeError`, `HtmlParser`, `Scorer`, `IndustryAverageProvider`, `IndustryAverageCache` from existing modules
    - Implement `stock_screener(ticker, stock_type, api_key, no_cache, refresh) -> dict` tool decorated with `@mcp.tool`
    - Validate mutual exclusion: if both `no_cache` and `refresh` are True, return `{"error": "..."}`
    - Resolve API key: use `api_key` parameter if non-empty, else fall back to `os.environ.get("OPENAI_API_KEY")`, return `{"error": "..."}` if neither available
    - Parse comma-separated `stock_type` string, validate each against `RatioConfigResolver`, return `{"error": "..."}` on invalid type
    - Fetch finviz page once via `FinvizScraper.fetch_page(ticker)`, catch `ScrapeError` and return `{"error": "..."}`
    - Parse HTML for price, sector, industry via `HtmlParser`
    - Loop per stock type: resolve ratios, parse values, check/update cache respecting `no_cache`/`refresh` flags, fetch industry averages on miss, compute score via `Scorer`
    - Build and return structured result dict with `ticker`, `price`, `sector`, `industry`, `stock_types` (list of per-type dicts with `type`, `score`, `max_score`, `ratios`), `total_score`, `total_max`, `percentage`
    - Wrap all operations in try-except — return `{"error": "..."}` on any unexpected failure
    - _Requirements: 24.2, 24.3, 24.5, 24.6, 24.7, 24.8, 24.9, 24.10, 24.11_
  - [x] 30.3 Implement `screen_stock` prompt in `stock_screener/mcp_server.py`
    - Implement `screen_stock(ticker: str, stock_type: str) -> str` decorated with `@mcp.prompt`
    - The `ticker` parameter accepts one or more comma-separated ticker symbols (e.g., `"AAPL"` or `"AAPL,MSFT,GOOG"`)
    - Split the `ticker` string on commas, strip whitespace, and uppercase each ticker
    - For a single ticker, return a prompt string that instructs the LLM to:
      (a) Call the `stock_screener` tool once with the provided ticker and stock type
      (b) Display a banner header showing the ticker, price, and stock types before any tables
      (c) Render a separate markdown table per stock type with columns: Ratio, Optimal Value, Industry Average, Real-Time Value, Importance
      (d) Show the score per stock type above each table (e.g., "value: 2 / 10")
      (e) End with the cumulative Investment Score as a percentage
    - For multiple tickers, return a prompt string that instructs the LLM to:
      (a) Call the `stock_screener` tool once per ticker (all calls can be made in parallel)
      (b) Render results for each ticker separately, one after another
      (c) Use the same per-ticker format as single-ticker (banner header, per-type tables with scores, Investment Score)
      (d) Separate each ticker's output with a horizontal rule (`---`)
    - _Requirements: 24.14, 24.15, 24.16_

- [x] 31. Register MCP server in workspace configuration
  - [x] 31.1 Create or update `.kiro/settings/mcp.json` with the stock-screener server entry
    - Add `"stock-screener"` entry with `"command": "python"` and `"args": ["stock_screener/mcp_server.py"]`
    - Set `"disabled": false` and `"autoApprove": []`
    - If the file already exists, merge the new entry without overwriting existing servers
    - _Requirements: 24.13_

- [x] 32. Checkpoint - Verify MCP server integration
  - Ensure `stock_screener/mcp_server.py` is syntactically correct and importable
  - Ensure `fastmcp` package is installed
  - Ensure `get_ratio_definitions` tool returns correct ratio data for all three stock types (div, growth, value)
  - Ensure `stock_screener` tool returns structured data with scores for a valid ticker
  - Ensure `no_cache` and `refresh` flags work correctly through the MCP tool
  - Ensure mutual exclusion of `no_cache` and `refresh` returns an error dict
  - Ensure missing API key returns an error dict
  - Ensure invalid stock type returns an error dict
  - Ensure `.kiro/settings/mcp.json` contains the workspace-level server registration
  - Ensure `screen_stock` prompt returns a well-formed instruction string that references the banner header, table format, scores, and Investment Score
  - Ensure `screen_stock` prompt handles single ticker input (e.g., `"AAPL"`) with a single tool call instruction
  - Ensure `screen_stock` prompt handles multi-ticker input (e.g., `"AAPL,MSFT,GOOG"`) with per-ticker tool call instructions and horizontal rule separators
  - Run mypy and pylint to verify no type or lint errors
  - Ask the user if questions arise.

- [x] 33. Add cross-platform file locking to IndustryAverageCache
  - [x] 33.1 Install the `filelock` package
    - Run `pip install filelock` in the project's pyenv environment
    - Verify the package is importable: `python -c "from filelock import FileLock, Timeout"`
    - _Requirements: 25.5_
  - [x] 33.2 Update `stock_screener/cache.py` to use `filelock.FileLock` for concurrent access safety
    - Add `from filelock import FileLock` and `from filelock import Timeout` imports
    - Add class constants `_LOCK_FILE: str = "cache.json.lock"` and `_LOCK_TIMEOUT_SECONDS: int = 10`
    - In `__init__`, compute `self._lock_path: Path = self._cache_path.parent / self._LOCK_FILE` and create `self._lock: FileLock = FileLock(str(self._lock_path), timeout=self._LOCK_TIMEOUT_SECONDS)`
    - Update `get()` to wrap the entire read operation inside `with self._lock:` context manager
    - Update `put()` to wrap the entire read-modify-write cycle inside `with self._lock:` context manager
    - Add `except Timeout:` handler to both `get()` and `put()` that logs a warning via Rich console and falls back to unlocked operation
    - Remove any existing raw file I/O locking code if present (e.g., `fcntl`, `os.open` for lock files)
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_

- [x] 34. Checkpoint - Verify file locking works for concurrent cache access
  - Ensure `stock_screener/cache.py` imports `filelock` correctly and is syntactically valid
  - Ensure `~/.stock_screener/cache.json.lock` is created when the cache is accessed
  - Ensure that running multiple stock screener MCP tool calls in parallel (e.g., 6 tickers with `growth,value`) results in all stock types being correctly persisted in `cache.json` for every ticker
  - Ensure the lock timeout fallback works: if the lock cannot be acquired within 10 seconds, the operation proceeds with a warning rather than crashing
  - Run mypy and pylint to verify no type or lint errors
  - Ask the user if questions arise.

- [x] 35. Clear stale cache and verify new value ratio set
  - [x] 35.1 Delete the cache file at `~/.stock_screener/cache.json`
    - The entire cache file contains stale "value" type entries with old ratio names (P/E, P/B) that are incompatible with the new ratio set (EV/Revenue, Earnings Yield)
    - Delete `~/.stock_screener/cache.json` entirely rather than selectively removing entries
    - The next run will re-fetch fresh industry averages for all stock types with the correct ratio names
    - _Requirements: 13.4_

- [x] 36. Checkpoint - Verify new value ratio set works end-to-end
  - Ensure `stock_screener/ratios.py` is syntactically correct and importable with the updated value ratio set
  - Ensure `RatioConfigResolver.get_ratio_set("value")` returns exactly 10 ratios with the new composition
  - Ensure `HtmlParser.parse_ratios()` correctly computes Earnings Yield from P/E for a stock with a valid P/E value
  - Ensure `HtmlParser.parse_ratios()` returns "N/A" for Earnings Yield when P/E is missing or invalid
  - Ensure `EV/Revenue` correctly maps to the finviz label "EV/Sales" and extracts the value
  - Ensure the `get_ratio_definitions` MCP tool returns the updated value ratio definitions (EV/Revenue and Earnings Yield present, P/E and P/B absent)
  - Ensure the `stock_screener` MCP tool returns correct results with the new value ratio set
  - Ensure the industry average prompt for "value" stock type now includes both percentage and multiple format instructions (since Earnings Yield is `format_type="percentage"`)
  - Run mypy and pylint to verify no type or lint errors
  - Ask the user if questions arise.
