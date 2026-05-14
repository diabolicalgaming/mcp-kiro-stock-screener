# Requirements Document

## Introduction

A Python command-line stock screener application that retrieves and displays financial ratios for stocks based on their classification type (dividend, growth, or value). The application accepts a stock ticker symbol and stock type as command-line arguments, scrapes relevant ratio data from finviz.com, and presents the results in a formatted five-column table with ratio names, optimal values, real-time values, industry averages, and importance descriptions. Industry-average values are retrieved via the OpenAI API based on the ticker's industry, and the Industry Average column uses the same conditional color scheme as the Real-Time Value column. The OpenAI API key is provided by the user as a CLI argument or environment variable.

## Glossary

- **Screener**: The Python CLI application that retrieves and displays stock ratios.
- **Stock_Ticker**: A unique alphabetic abbreviation (1-5 uppercase letters) identifying a publicly traded company (e.g., AAPL, MSFT).
- **Stock_Type**: One of three classification categories: "div" (dividend), "growth", or "value".
- **Ratio**: A named financial metric retrieved from finviz.com (e.g., P/E, Dividend Yield, EPS growth).
- **Ratio_Set**: The collection of ratios relevant to a specific Stock_Type.
- **Finviz_Page**: The stock quote page at finviz.com from which ratio data is scraped.
- **Results_Table**: A formatted text table with five columns: Ratio, Optimal Value, Real-Time Value, Industry Average, and Importance.
- **Current_Price**: The current trading price of the stock as displayed on the Finviz_Page.
- **IndustryAverageProvider**: A new component responsible for fetching industry-average ratio values from the OpenAI API.
- **Industry_Average_Column**: The new table column displaying industry-average values for each ratio.
- **OpenAI_API**: The OpenAI chat completions API used to retrieve industry-average ratio data.
- **API_Key**: The OpenAI API key required to authenticate requests to the OpenAI API.
- **Header_Line**: A colored output line above the Results_Table in the format: "<Ticker> - <Price> (<Stock_Type>)".
- **Optimal_Value**: A short description of the ideal or healthy range for a given ratio.
- **Importance**: A short description explaining why the ratio matters for the given stock type.
- **Stock_Type_List**: A comma-separated string of one or more valid stock types provided as the second positional CLI argument (e.g. `growth,value,div`).
- **VALID_STOCK_TYPES**: The set of recognized stock type identifiers: `div`, `growth`, `value`.
- **IndustryAverageCache**: A new component responsible for persisting and retrieving cached industry-average data from a local JSON file.
- **Cache_TTL**: The time-to-live duration (in days) after which a cached entry is considered expired and must be refreshed.
- **Sector**: The broad market sector of the stock as displayed on the Finviz_Page (e.g., "Technology", "Healthcare").
- **Industry**: The specific industry classification of the stock as displayed on the Finviz_Page (e.g., "Consumer Electronics", "Drug Manufacturers").
- **Calculated_Ratio**: A ratio whose value is not directly scraped from a single finviz label but is derived by combining two or more scraped values using a formula (e.g., FCF Margin = P/S ÷ P/FCF × 100).
- **Source_Ratio**: A finviz ratio used as an input to compute a Calculated_Ratio (e.g., P/S and P/FCF are source ratios for FCF Margin).

## Requirements

### Requirement 1: Command-Line Argument Parsing

**User Story:** As a user, I want to provide a stock ticker and stock type via the command line, so that I can quickly screen any stock without a GUI.

#### Acceptance Criteria

1. WHEN the user provides a valid Stock_Ticker and Stock_Type, THE Screener SHALL accept the arguments and proceed to data retrieval.
2. WHEN the user provides fewer than two arguments, THE Screener SHALL display a usage message indicating the required arguments and exit with a non-zero status code.
3. WHEN the user provides an unrecognized Stock_Type, THE Screener SHALL display an error message listing the valid stock types ("div", "growth", "value") and exit with a non-zero status code.
4. THE Screener SHALL accept Stock_Ticker values in a case-insensitive manner and normalize the ticker to uppercase before use.
5. WHEN the user provides a ticker containing commas (e.g., "NKE,DECK"), THE ArgumentParser SHALL display an error message stating that only one ticker is allowed and suggesting the MCP server for multiple tickers, and exit with a non-zero status code.
6. WHEN the user provides a ticker that does not match the valid ticker format (letters only, with an optional single hyphen for share classes, e.g., "BRK-B"), THE ArgumentParser SHALL display an error message indicating the invalid ticker format and exit with a non-zero status code.
7. THE ArgumentParser SHALL enforce ticker validation at the argparse `type` level via a custom validation function, so that invalid tickers are rejected before any further argument processing occurs.
8. THE valid ticker format SHALL be defined by the regex pattern `^[a-zA-Z]+(-[a-zA-Z]+)?$`, which accepts alphabetic tickers (e.g., "AAPL", "NKE") and share-class tickers with a single hyphen (e.g., "BRK-B", "BF-B"), while rejecting dots, numbers, spaces, and other special characters.

### Requirement 2: Stock Type Ratio Mapping

**User Story:** As a user, I want each stock type to have its own set of relevant ratios, so that I see only the metrics that matter for my investment strategy.

#### Acceptance Criteria

1. WHEN the Stock_Type is "div", THE Screener SHALL use the dividend Ratio_Set containing: Dividend Yield, Dividend Payout, and Dividend Growth Rate (3-5 yr).
2. WHEN the Stock_Type is "growth", THE Screener SHALL use the growth Ratio_Set containing: Gross Margin, Operating Margin, EPS YoY, Revenue Growth YoY, Revenue Growth 3–5 Year CAGR, and FCF Margin.
3. WHEN the Stock_Type is "value", THE Screener SHALL use the value Ratio_Set containing: Beta, Forward P/E, PEG, EV/EBITDA, P/S, EV/Revenue, Earnings Yield, Debt/EQ, LT Debt/EQ, and Current Ratio.
4. EACH RatioInfo SHALL include a `format_type` field with valid values `"percentage"` or `"multiple"` to indicate whether the ratio is a percentage-based metric or a plain multiple/coefficient.
5. ALL ratios in the "div" Ratio_Set SHALL have `format_type="percentage"`.
6. ALL ratios in the "growth" Ratio_Set SHALL have `format_type="percentage"`.
7. ALL ratios in the "value" Ratio_Set SHALL have `format_type="multiple"`, EXCEPT for Earnings Yield which SHALL have `format_type="percentage"`.
8. THE Earnings Yield ratio SHALL be a Calculated_Ratio derived from the trailing P/E ratio using the formula: Earnings Yield = (1 / P_E) × 100. THE `finviz_label` field SHALL be set to an empty string `""` since it is not scraped directly. THE `source_labels` field SHALL be `["P/E"]` and the `calculation` field SHALL be `"inverse_pe_times_100"`.
9. WHEN computing a Calculated_Ratio, THE HtmlParser SHALL extract the numeric values for each label in `source_labels` from the Finviz_Page, dispatch to the appropriate calculation function based on the `calculation` field, and return the result formatted as a percentage string (e.g., "3.29%"). For Earnings Yield (`calculation="inverse_pe_times_100"`), the formula is: (1 / P_E) × 100.
10. IF any source value required by a Calculated_Ratio is missing, non-numeric, zero, or negative (where division is involved) on the Finviz_Page, THEN THE HtmlParser SHALL return "N/A" for that Calculated_Ratio.
11. THE EV/Revenue ratio SHALL use the finviz label `"EV/Sales"` and display as "EV/Revenue" in the results table.

### Requirement 3: Optimal Value Descriptions

**User Story:** As a user, I want to see the optimal range for each ratio, so that I can quickly judge whether a stock's metrics are healthy.

#### Acceptance Criteria

1. THE Screener SHALL display an Optimal_Value description for each ratio in the dividend Ratio_Set as follows:
   - Dividend Yield: ">=2-5%"
   - Dividend Payout: ">=30-70%"
   - Dividend Growth Rate (3-5 yr): ">=5-10% per year"

2. THE Screener SHALL display an Optimal_Value description for each ratio in the growth Ratio_Set as follows:
   - Gross Margin: ">=40%"
   - Operating Margin: ">=15%"
   - EPS YoY: ">=15% annually"
   - Revenue Growth YoY: ">=15%"
   - Revenue Growth 3–5 Year CAGR: ">=10%"
   - FCF Margin: ">=10%"

3. THE Screener SHALL display an Optimal_Value description for each ratio in the value Ratio_Set as follows:
   - Beta: "<1.0 low risk, >1.0 volatile"
   - P/E: ">=20-50 (sector), <sector undervalued"
   - Forward P/E: "<industry avg, >=10-20 stability"
   - PEG: "<1.0"
   - P/B: "<1.5 stability, <1.0 undervaluation"
   - P/S: "<2.0, <1.0 cheap"
   - EV/EBITDA: "<10 signals undervaluation"
   - Debt/EQ: "<1.0 for value stocks"
   - LT Debt/EQ: "<1.0 most sectors, <0.5 stable for dividend stocks"
   - Current Ratio: ">1.5 comfortable, <1.0 liquidity issues"

### Requirement 4: Importance Descriptions

**User Story:** As a user, I want to understand why each ratio matters, so that I can make informed investment decisions.

#### Acceptance Criteria

1. THE Screener SHALL display an Importance description for each ratio in the dividend Ratio_Set as follows:
   - Dividend Yield: "% of share price paid as dividends yearly."
   - Dividend Payout: "% of earnings paid as dividend."
   - Dividend Growth Rate (3-5 yr): "Shows the company can reliably increase payouts over time."

2. THE Screener SHALL display an Importance description for each ratio in the growth Ratio_Set as follows:
   - Gross Margin: "% of revenue left after production costs."
   - Operating Margin: "Profit from core business before taxes."
   - EPS YoY: "Shows how fast profits are growing."
   - Revenue Growth YoY: "Shows top-line revenue expansion year over year."
   - Revenue Growth 3–5 Year CAGR: "Average revenue growth over the past 3–5 years."
   - FCF Margin: "Measures how much revenue turns into cash."

3. THE Screener SHALL display an Importance description for each ratio in the value Ratio_Set as follows:
   - Beta: "Measures volatility vs overall market."
   - P/E: "How much investors pay for $1 of earnings."
   - Forward P/E: "Shows if the stock is cheap or expensive based on future earnings."
   - PEG: "PEG <1.0 suggests undervalued relative to growth prospects."
   - P/B: "Compares market value to net assets."
   - P/S: "Compares price to annual revenue."
   - EV/EBITDA: "Compares total company value to operating cash earnings."
   - Debt/EQ: "Shows reliance on debt vs own capital."
   - LT Debt/EQ: "Indicates financial stability and how safely dividends can be maintained."
   - Current Ratio: "Ability to cover ST liabilities with ST assets."

### Requirement 5: Data Retrieval from Finviz

**User Story:** As a user, I want the application to fetch live ratio data from finviz.com, so that I always see up-to-date financial metrics.

#### Acceptance Criteria

1. WHEN a valid Stock_Ticker and Stock_Type are provided, THE Screener SHALL send an HTTP GET request to the Finviz_Page for the given Stock_Ticker.
2. THE Screener SHALL parse the HTML response from the Finviz_Page and extract the values for each ratio in the selected Ratio_Set.
3. THE Screener SHALL parse the HTML response from the Finviz_Page and extract the Current_Price for the given Stock_Ticker.
4. WHEN a finviz ratio value contains multiple numeric tokens (e.g., `"4.23 (2.91%)"` for Dividend Yield or `"5.04% 6.13%"` for Dividend Growth Rate), THE Scorer SHALL extract and use the last numeric token for comparison against the industry average. The table display SHALL continue to show the original unmodified finviz value.
5. IF the HTTP request to finviz.com fails with a non-200 status code, THEN THE Screener SHALL display an error message including the status code and exit with a non-zero status code.
6. IF a network error occurs during the HTTP request, THEN THE Screener SHALL display a descriptive error message and exit with a non-zero status code.
7. IF a ratio from the Ratio_Set is not found on the Finviz_Page, THEN THE Screener SHALL display "N/A" as the value for that ratio.

### Requirement 6: Results Table Output

**User Story:** As a user, I want the results displayed in a clean five-column table, so that I can quickly read and compare the financial ratios alongside their context and industry benchmarks.

#### Acceptance Criteria

1. WHEN ratio data has been retrieved, THE Screener SHALL display a Results_Table to standard output containing five columns in this order: Ratio, Optimal Value, Real-Time Value, Industry Average, Importance.
2. THE Screener SHALL display a Header_Line above the Results_Table in the format: "<Ticker> - <Price> (<Stock_Type>)".
3. THE Screener SHALL render the Ticker portion of the Header_Line in light blue, the "- <Price>" portion (including currency symbol) in light green, and the "(<Stock_Type>)" portion in black.
4. THE Screener SHALL align all five columns in the Results_Table so that values are visually aligned.
5. WHEN all ratios are successfully retrieved, THE Screener SHALL exit with a zero status code.

### Requirement 7: HTML Parsing

**User Story:** As a developer, I want a reliable parser for the finviz HTML page, so that ratio extraction is accurate and maintainable.

#### Acceptance Criteria

1. WHEN the Finviz_Page HTML is received, THE Screener SHALL parse the HTML using a structured parser to locate ratio values by their label text.
2. IF the HTML structure of the Finviz_Page changes such that a ratio label cannot be located, THEN THE Screener SHALL display "N/A" for that ratio rather than crashing.
3. THE Screener SHALL handle ratio values that contain special characters (e.g., "%", "-") and preserve them as-is in the output.
4. WHEN finviz.com presents a cookie consent prompt, THE Screener SHALL handle the consent by including the appropriate cookie headers in the HTTP request to bypass the popup and access the stock data directly.


### Requirement 8: Accept OpenAI API Key

**User Story:** As a user, I want to provide my OpenAI API key to the application, so that the application can authenticate with the OpenAI API to fetch industry averages.

#### Acceptance Criteria

1. WHEN the user provides the `--api-key` CLI argument, THE ArgumentParser SHALL accept and store the API key value as a string.
2. WHEN the `--api-key` CLI argument is not provided, THE ArgumentParser SHALL read the API key from the `OPENAI_API_KEY` environment variable.
3. IF neither the `--api-key` argument nor the `OPENAI_API_KEY` environment variable is set, THEN THE Screener SHALL print an error message to stderr and exit with code 1.

### Requirement 9: Fetch Industry Averages via OpenAI API

**User Story:** As a user, I want the application to fetch industry-average values for each financial ratio, so that I can compare a stock's real-time values against its industry benchmarks.

#### Acceptance Criteria

1. WHEN a valid API_Key and Stock_Ticker are provided, THE IndustryAverageProvider SHALL send a prompt to the OpenAI_API requesting industry-average values for only the ratio names that belong to the active Ratio_Set for the given Stock_Type.
2. THE IndustryAverageProvider SHALL NOT request industry-average values for ratios outside the active Ratio_Set.
3. THE IndustryAverageProvider SHALL include the Stock_Ticker and the Stock_Type in the prompt so the OpenAI_API can determine the correct industry context.
4. THE prompt SHALL explicitly list every ratio name in the active Ratio_Set and instruct the OpenAI_API to return a value for each one, ensuring no ratio is omitted from the response.
5. THE prompt SHALL instruct the OpenAI_API to provide industry-average values for the current year, ensuring the returned data reflects the most recent available estimates rather than historical data.
6. THE IndustryAverageProvider SHALL parse the OpenAI_API response into a dictionary mapping each ratio name to its industry-average value as a string, and the dictionary SHALL contain an entry for every ratio in the active Ratio_Set.
7. THE prompt sent to the OpenAI_API SHALL be concise and token-efficient, avoiding unnecessary verbosity, examples, or repeated instructions, to minimize API usage costs.
8. IF the OpenAI_API returns a 429 (rate limit / insufficient funds) error, THEN THE IndustryAverageProvider SHALL log a descriptive error message to the console indicating that the account does not have sufficient funds and return "N/A" for all ratio names in the active Ratio_Set.
9. IF the OpenAI_API returns any other error or an unparseable response, THEN THE IndustryAverageProvider SHALL return "N/A" for all ratio names in the active Ratio_Set.
10. IF the OpenAI_API response omits a value for a specific ratio despite being requested, THEN THE IndustryAverageProvider SHALL use "N/A" as the value for that ratio.

### Requirement 10: Add Industry Average Column to DataFrame

**User Story:** As a user, I want the industry-average data included in the output table, so that I can see it alongside the other ratio data.

#### Acceptance Criteria

1. THE TableRenderer SHALL build the DataFrame with five columns in this order: Ratio, Optimal Value, Industry Average, Real-Time Value, Importance.
2. WHEN industry-average values are provided, THE TableRenderer SHALL populate the Industry_Average_Column with the corresponding value for each ratio row.
3. WHEN an industry-average value is "N/A" for a ratio, THE TableRenderer SHALL display "N/A" in the Industry_Average_Column for that row.

### Requirement 11: Apply Conditional Coloring to Industry Average Column

**User Story:** As a user, I want the Industry Average column to use the same color scheme as the Real-Time Value column, so that I can quickly assess whether industry averages fall within optimal ranges.

#### Acceptance Criteria

1. WHEN an industry-average value is negative, THE TableRenderer SHALL render that cell in red.
2. WHEN an industry-average value falls within the optimal range defined by the corresponding RatioInfo, THE TableRenderer SHALL render that cell in bright_green.
3. WHEN an industry-average value is non-negative and outside the optimal range, THE TableRenderer SHALL render that cell in the default style.
4. WHEN an industry-average value is "N/A", THE TableRenderer SHALL render that cell in the default style.

### Requirement 12: Integrate Industry Average Retrieval into Application Pipeline

**User Story:** As a user, I want the industry-average retrieval to be part of the normal application flow, so that the data appears automatically when I run the screener.

#### Acceptance Criteria

1. WHEN the application pipeline executes, THE Screener SHALL call the IndustryAverageProvider after resolving the Ratio_Set and before building the DataFrame.
2. THE Screener SHALL pass the API_Key, Stock_Ticker, Stock_Type, and active Ratio_Set to the IndustryAverageProvider.
3. THE Screener SHALL pass the industry-average values dictionary to the TableRenderer for inclusion in the DataFrame.
4. IF the IndustryAverageProvider encounters an error, THEN THE Screener SHALL log the error to the console and continue rendering the table with "N/A" values in the Industry_Average_Column.

### Requirement 13: Cache Industry Average Data Locally

**User Story:** As a user, I want industry-average data to be cached locally, so that repeated runs for the same ticker and stock type return consistent results without unnecessary API calls.

#### Acceptance Criteria

1. WHEN industry-average data is successfully fetched from the OpenAI API, THE Screener SHALL persist the data to a local JSON cache file at `~/.stock_screener/cache.json`.
2. THE cache SHALL be structured by ticker at the top level, with stock type as the second level, so that a single ticker can hold cached data for multiple stock types (e.g., `{"AAPL": {"div": {...}, "growth": {...}, "value": {...}}}`).
3. EACH cached entry SHALL include a `timestamp` (ISO 8601 format) and an `averages` dictionary mapping ratio names to their industry-average values.
4. WHEN a cached entry exists for the requested ticker and stock type and the entry is not expired, THE Screener SHALL use the cached data instead of calling the OpenAI API.
5. THE cache TTL (time-to-live) SHALL default to 7 days and SHALL be configurable via a class-level constant `DEFAULT_TTL_DAYS` in the `IndustryAverageCache` class.
6. WHEN a cached entry is older than the configured TTL, THE Screener SHALL treat it as a cache miss and fetch fresh data from the OpenAI API.
7. IF the cache file cannot be read or written (e.g., permission error, corrupt JSON), THE Screener SHALL log a warning and continue without caching rather than crashing.

### Requirement 14: CLI Flags for Cache Control

**User Story:** As a user, I want CLI flags to control caching behavior, so that I can force a refresh or bypass the cache entirely when needed.

#### Acceptance Criteria

1. THE ArgumentParser SHALL accept a `--no-cache` flag that, when provided, disables both reading from and writing to the cache for that run.
2. THE ArgumentParser SHALL accept a `--refresh` flag that, when provided, skips reading from the cache but writes fresh API results back to the cache.
3. THE `--no-cache` and `--refresh` flags SHALL be mutually exclusive; if both are provided, THE ArgumentParser SHALL display an error message and exit with a non-zero status code.
4. WHEN neither `--no-cache` nor `--refresh` is provided, THE Screener SHALL use the default caching behavior (read from cache if valid, write on miss).
5. THE `parse()` method SHALL return a 5-tuple: `(ticker, stock_type, api_key, no_cache, refresh)`.

### Requirement 15: Extract Sector and Industry from Finviz Page

**User Story:** As a user, I want the application to extract the stock's sector and industry from finviz.com, so that the OpenAI prompt can use specific sector context to return accurate industry-average values for all stock types including growth metrics.

#### Acceptance Criteria

1. WHEN the Finviz_Page HTML is parsed, THE HtmlParser SHALL extract the sector and industry from the `div` element with class `quote-links whitespace-nowrap gap-8`.
2. THE HtmlParser SHALL extract the text content of the first `<a>` tag within that `div` as the Sector (e.g., "Technology") and the second `<a>` tag as the Industry (e.g., "Consumer Electronics").
3. THE `parse_sector_industry()` method SHALL return a `tuple[str, str]` of `(sector, industry)`.
4. IF the sector or industry cannot be found in the HTML, THE HtmlParser SHALL return `"Unknown"` for the missing value rather than crashing.
5. THE Screener SHALL pass the extracted sector and industry to the IndustryAverageProvider for inclusion in the OpenAI prompt.
6. THE IndustryAverageProvider `_build_prompt()` method SHALL include the sector and industry in the prompt to provide specific sector context. THE method SHALL use each ratio's `format_type` metadata to generate format-specific instructions — requesting percentage strings (e.g., "15%") for `"percentage"` ratios and plain number strings without "%" (e.g., "22.0") for `"multiple"` ratios.
7. THE IndustryAverageProvider `_build_prompt()` method SHALL instruct the model that for growth rate metrics, it should provide the sector median growth rate.
8. THE system message sent to the OpenAI API SHALL instruct the model to return JSON only with no explanation and that every value must be a non-empty string.
9. WHEN the stock type is "div" or "growth" (all ratios are `format_type="percentage"`), THE prompt SHALL request percentage strings for all ratios, preserving existing correct behavior.
10. WHEN the stock type is "value" (all ratios are `format_type="multiple"`), THE prompt SHALL request plain number strings without "%" for all ratios.

### Requirement 16: Parse Comma-Separated Stock Types

**User Story:** As a user, I want to provide multiple stock types as a comma-separated string, so that I can retrieve ratio data for several stock types in one command.

#### Acceptance Criteria

1. WHEN a Stock_Type_List is provided as the second positional argument, THE ArgumentParser SHALL split the string on commas and return a list of individual stock type strings.
2. WHEN the Stock_Type_List contains duplicate stock type entries, THE ArgumentParser SHALL remove duplicates and preserve the order of first occurrence.
3. WHEN any individual stock type in the Stock_Type_List is not a member of VALID_STOCK_TYPES, THE ArgumentParser SHALL print an error message identifying the invalid stock type and exit with code 1.
4. WHEN all individual stock types in the Stock_Type_List are members of VALID_STOCK_TYPES, THE ArgumentParser SHALL return the validated list of stock types to the caller.
5. THE ArgumentParser SHALL continue to accept a single stock type without a comma as a valid Stock_Type_List containing one element.

### Requirement 17: Single HTML Fetch Per Ticker

**User Story:** As a user, I want the application to fetch the ticker's web page only once regardless of how many stock types I request, so that the command runs efficiently.

#### Acceptance Criteria

1. WHEN multiple stock types are requested for a single ticker, THE StockScreenerApp SHALL invoke FinvizScraper.fetch_page exactly once for that ticker.
2. THE StockScreenerApp SHALL reuse the fetched HTML and the parsed price, sector, and industry values across all requested stock types.

### Requirement 18: Single Banner Header Display

**User Story:** As a user, I want to see the ticker name, price, and all requested stock types displayed once at the top, so that the output is clean and not repetitive.

#### Acceptance Criteria

1. WHEN multiple stock types are requested, THE TableRenderer SHALL render the banner header exactly once before all ratio tables.
2. THE banner header SHALL display the format `<Ticker> - <Price> (<StockType1>, <StockType2>, ...)` listing all requested stock types in the order they were provided.
3. WHEN a single stock type is requested, THE banner header SHALL display the format `<Ticker> - <Price> (<StockType>)`.

### Requirement 19: Per-Stock-Type Table Rendering

**User Story:** As a user, I want to see a separate ratio table for each requested stock type, so that I can compare different screening perspectives for the same ticker.

#### Acceptance Criteria

1. WHEN multiple stock types are requested, THE StockScreenerApp SHALL produce one ratio table per stock type in the order the stock types were provided.
2. WHEN rendering multiple ratio tables, THE TableRenderer SHALL separate each table with a stock type label and a blank line for visual clarity.
3. THE TableRenderer SHALL render each ratio table with the same column structure and styling used for single stock type output.

#### Example Output

**Single stock type** (`python -m stock_screener.main AAPL div`):

```
╭──────────────────────────────────────╮
│        AAPL  $198.50  (div)          │
╰──────────────────────────────────────╯

div: 0 / 3
┌──────────────────────┬──────────────────┬──────────────────┬─────────────────┬────────────────────────────────────────────┐
│ Ratio                │ Optimal Value    │ Industry Average │ Real-Time Value │ Importance                                 │
├──────────────────────┼──────────────────┼──────────────────┼─────────────────┼────────────────────────────────────────────┤
│ Dividend Yield       │ >=2-5%           │ 1.8%             │ 0.55%           │ % of share price paid as dividends yearly. │
│ Dividend Payout      │ >=30-70%         │ 38%              │ 15.6%           │ % of earnings paid as dividend.            │
│ Dividend Growth Rate │ >=5-10% per year │ 7.2%             │ 4.3%            │ Shows the company can reliably increase... │
└──────────────────────┴──────────────────┴──────────────────┴─────────────────┴────────────────────────────────────────────┘

╭──────────────────────────────────────╮
│  Investment Score: 0 / 3 (0.0%)      │
╰──────────────────────────────────────╯
```

**Multiple stock types** (`python -m stock_screener.main AAPL div,value`):

```
╭──────────────────────────────────────────╮
│      AAPL  $198.50  (div, value)         │
╰──────────────────────────────────────────╯

div: 0 / 3
┌──────────────────────┬──────────────────┬──────────────────┬─────────────────┬────────────────────────────────────────────┐
│ Ratio                │ Optimal Value    │ Industry Average │ Real-Time Value │ Importance                                 │
├──────────────────────┼──────────────────┼──────────────────┼─────────────────┼────────────────────────────────────────────┤
│ Dividend Yield       │ >=2-5%           │ 1.8%             │ 0.55%           │ % of share price paid as dividends yearly. │
│ Dividend Payout      │ >=30-70%         │ 38%              │ 15.6%           │ % of earnings paid as dividend.            │
│ Dividend Growth Rate │ >=5-10% per year │ 7.2%             │ 4.3%            │ Shows the company can reliably increase... │
└──────────────────────┴──────────────────┴──────────────────┴─────────────────┴────────────────────────────────────────────┘

value: 2 / 10
┌───────────────┬─────────────────────────────────────┬──────────────────┬─────────────────┬────────────────────────────────────────────────┐
│ Ratio         │ Optimal Value                       │ Industry Average │ Real-Time Value │ Importance                                     │
├───────────────┼─────────────────────────────────────┼──────────────────┼─────────────────┼────────────────────────────────────────────────┤
│ Beta          │ <1.0 low risk, >1.0 volatile        │ 1.15             │ 1.24            │ Measures volatility vs overall market.         │
│ P/E           │ >=20-50 (sector), <sector underval. │ 28.5             │ 33.2            │ How much investors pay for $1 of earnings.     │
│ Forward P/E   │ <industry avg, >=10-20 stability    │ 25.0             │ 22.1            │ Shows if stock is cheap/expensive on future.   │
│ PEG           │ <1.0                                │ 1.8              │ 1.5             │ PEG <1.0 suggests undervalued rel. to growth.  │
│ P/B           │ <1.5 stability, <1.0 undervaluation │ 6.2              │ 48.9            │ Compares market value to net assets.           │
│ P/S           │ <2.0, <1.0 cheap                    │ 5.1              │ 8.5             │ Compares price to annual revenue.              │
│ EV/EBITDA     │ <10 signals undervaluation          │ 18.0             │ 25.3            │ Compares total company value to op. cash.      │
│ Debt/EQ       │ <1.0 for value stocks               │ 1.5              │ 1.87            │ Shows reliance on debt vs own capital.         │
│ LT Debt/EQ    │ <1.0 most sectors, <0.5 stable      │ 1.2              │ 1.64            │ Indicates financial stability.                 │
│ Current Ratio │ >1.5 comfortable, <1.0 liquidity    │ 1.3              │ 0.99            │ Ability to cover ST liabilities with ST assets.│
└───────────────┴─────────────────────────────────────┴──────────────────┴─────────────────┴────────────────────────────────────────────────┘

╭──────────────────────────────────────────╮
│   Investment Score: 2 / 13 (15.4%)       │
╰──────────────────────────────────────────╯
```

**Color scheme for stock type label:** `{stock_type}:` in cyan, `{score}` and `{max}` in bright_magenta (bright pink), `/` in white.

**Investment Score banner:** Appears once at the end with the cumulative total score across all selected stock types. Banner border in bright_blue. Score percentage color: green (>70%), yellow (50-70%), red (<50%).

**Scoring rules:**

1. FOR growth and value stock types, a ratio SHALL score one point when the real-time value beats the industry average based on the ratio's compare direction (`higher_is_better` or `lower_is_better`).
2. FOR the dividend stock type, a ratio SHALL score one point only when BOTH of the following conditions are met: (a) the real-time value beats the industry average based on the ratio's compare direction, AND (b) the real-time value falls within the optimal value range defined by the corresponding RatioInfo.
3. IF either condition fails for a dividend ratio, THEN no point SHALL be awarded for that ratio.

### Requirement 20: Per-Stock-Type Cache Operations

**User Story:** As a user, I want the cache to store and retrieve industry averages independently for each stock type, so that cached data remains granular and accurate.

#### Acceptance Criteria

1. WHEN multiple stock types are requested, THE IndustryAverageCache SHALL perform a separate cache lookup for each stock type using the existing per-ticker per-stock-type key structure.
2. WHEN multiple stock types are requested, THE IndustryAverageCache SHALL store each stock type's industry averages as a separate entry under the ticker key.
3. THE IndustryAverageCache SHALL not modify the existing cache key structure or file format.

### Requirement 21: Uniform Cache Flag Behavior

**User Story:** As a user, I want the `--no-cache` and `--refresh` flags to apply to all requested stock types uniformly, so that cache behavior is consistent and predictable.

#### Acceptance Criteria

1. WHEN the `--no-cache` flag is set and multiple stock types are requested, THE StockScreenerApp SHALL bypass the cache (both reading and writing) for every requested stock type.
2. WHEN the `--refresh` flag is set and multiple stock types are requested, THE StockScreenerApp SHALL ignore existing cached data and update the cache with fresh data for every requested stock type.
3. WHEN neither `--no-cache` nor `--refresh` is set, THE StockScreenerApp SHALL use cached industry averages for each stock type that has a valid cache entry and fetch fresh data only for stock types with missing or expired cache entries.
4. THE `--no-cache` and `--refresh` flags SHALL remain mutually exclusive as defined in Requirement 14; the existing argparse mutual exclusion logic SHALL apply unchanged.

### Requirement 22: Per-Stock-Type Industry Average Fetching

**User Story:** As a user, I want industry averages to be fetched separately for each stock type, so that the averages are specific to the ratio set of each stock type.

#### Acceptance Criteria

1. WHEN multiple stock types are requested, THE IndustryAverageProvider SHALL be called once per stock type that requires fresh industry average data.
2. THE IndustryAverageProvider SHALL receive the ratio set specific to each stock type when fetching averages.
3. IF the IndustryAverageProvider fails for one stock type, THEN THE StockScreenerApp SHALL use fallback "N/A" values for that stock type and continue processing the remaining stock types.

### Requirement 23: Updated Return Type from ArgumentParser

**User Story:** As a developer, I want the ArgumentParser to return a list of stock types instead of a single string, so that downstream code can iterate over the requested types.

#### Acceptance Criteria

1. THE ArgumentParser.parse method SHALL return a tuple of `(ticker, stock_types, api_key, no_cache, refresh)` where `stock_types` is a `list[str]`.
2. WHEN a single stock type is provided, THE ArgumentParser SHALL return a list containing that single stock type.

### Requirement 24: MCP Server Interface

**User Story:** As a developer, I want the stock screener exposed as an MCP (Model Context Protocol) server, so that LLM clients can invoke the screening pipeline programmatically without using the CLI.

#### Acceptance Criteria

1. THE project SHALL include a new file `stock_screener/mcp_server.py` that creates a FastMCP server instance named `"stock-screener"` using the `fastmcp` Python package.
2. THE `mcp_server.py` file SHALL import and reuse existing classes (`FinvizScraper`, `HtmlParser`, `RatioConfigResolver`, `Scorer`, `IndustryAverageProvider`, `IndustryAverageCache`) without modifying any existing source files.
3. THE MCP server SHALL expose a `stock_screener` tool that accepts a `ticker` (str), `stock_type` (str — comma-separated list of valid stock types), an optional `api_key` (str), an optional `no_cache` (bool, default False), and an optional `refresh` (bool, default False) parameter, and returns a structured dictionary containing the ticker, price, sector, industry, per-stock-type ratio data with real-time values, industry averages, scores, and a cumulative investment score.
4. THE MCP server SHALL expose a `get_ratio_definitions` tool that accepts a `stock_type` (str) parameter and returns the list of ratio definitions (name, optimal value, importance, format type, compare direction) for that stock type.
5. WHEN the `api_key` parameter is not provided to the `stock_screener` tool, THE MCP server SHALL fall back to reading the `OPENAI_API_KEY` environment variable.
6. WHEN the `stock_screener` tool encounters a scraping error, an invalid stock type, or an HTML parsing error, THE tool SHALL return a dictionary containing an `"error"` key with a descriptive message rather than raising an exception.
7. WHEN `no_cache` is True, THE `stock_screener` tool SHALL bypass the cache entirely (no reading, no writing), matching the behavior of the CLI `--no-cache` flag.
8. WHEN `refresh` is True, THE `stock_screener` tool SHALL ignore existing cached data but write fresh API results back to the cache, matching the behavior of the CLI `--refresh` flag.
9. WHEN both `no_cache` and `refresh` are True, THE `stock_screener` tool SHALL return a dictionary containing an `"error"` key indicating that the two options are mutually exclusive.
10. WHEN neither `no_cache` nor `refresh` is True, THE `stock_screener` tool SHALL use the existing `IndustryAverageCache` with default caching behavior (read from cache if valid, write on miss).
11. ALL tool return values SHALL be JSON-serializable dictionaries or lists — no Rich text, no Pandas DataFrames, and no styled terminal output.
12. THE `mcp_server.py` file SHALL include an `if __name__ == "__main__"` block that calls `mcp.run()` to start the server using the default stdio transport.
13. THE MCP server SHALL be registered as a workspace-level MCP server in `.kiro/settings/mcp.json` (not the global `~/.kiro/settings/mcp.json`) with a `"stock-screener"` entry that runs `python stock_screener/mcp_server.py`.
14. THE MCP server SHALL expose a `screen_stock` prompt via `@mcp.prompt` that accepts a `ticker` (str — one or more comma-separated ticker symbols, e.g. `"AAPL"` or `"AAPL,MSFT,GOOG"`) and `stock_type` (str) parameter and returns a prompt string instructing the LLM to: (a) call the `stock_screener` tool once per ticker (all calls can be made in parallel when multiple tickers are provided), (b) display a banner header per ticker showing the ticker, price, and stock types before any tables, (c) render a separate markdown table per stock type with columns Ratio, Optimal Value, Industry Average, Real-Time Value, Importance, (d) show the score per stock type above each table (e.g., "value: 2 / 10"), (e) end each ticker section with the cumulative Investment Score as a percentage, and (f) separate each ticker's output with a horizontal rule (`---`) when multiple tickers are provided.
15. WHEN a single ticker is provided to the `screen_stock` prompt, THE prompt SHALL instruct the LLM to call the `stock_screener` tool once and render a single set of results.
16. WHEN multiple comma-separated tickers are provided to the `screen_stock` prompt, THE prompt SHALL instruct the LLM to call the `stock_screener` tool once per ticker and render each ticker's results separately, one after another, separated by horizontal rules.

### Requirement 25: Cache File Locking for Concurrent Access Safety

**User Story:** As a user, I want the cache file to be safe from data loss when multiple stock screener processes run in parallel, so that industry-average data for all tickers and stock types is persisted correctly.

#### Acceptance Criteria

1. WHEN the IndustryAverageCache reads from or writes to the cache file, THE IndustryAverageCache SHALL acquire a file-level lock using the `filelock` package (`FileLock`) to prevent data loss from concurrent read-modify-write operations.
2. THE IndustryAverageCache SHALL acquire an exclusive lock before reading the cache file and release the lock only after writing the updated data back, ensuring that the entire read-modify-write cycle is atomic.
3. THE IndustryAverageCache SHALL use a separate lock file (e.g., `cache.json.lock`) for locking to avoid corrupting the cache data file itself.
4. IF the lock cannot be acquired within 10 seconds, THEN THE IndustryAverageCache SHALL proceed with the cache operation without locking and log a warning to the console rather than crashing.
5. THE file locking mechanism SHALL use the `filelock` package which provides cross-platform file locking compatible with macOS, Linux, and Windows.

#### Example Output

**`stock_screener` tool** — Input passed to the MCP server:

```json
{
  "ticker": "NVDA",
  "stock_type": "growth,value"
}
```

Output:

```json
{
  "ticker": "NVDA",
  "price": "199.64",
  "sector": "Technology",
  "industry": "Semiconductors",
  "stock_types": [
    {
      "type": "growth",
      "score": 6,
      "max_score": 6,
      "ratios": [
        {
          "name": "Gross Margin",
          "optimal": ">=40%",
          "industry_average": "53%",
          "realtime_value": "71.07%",
          "importance": "% of revenue left after production costs."
        },
        {
          "name": "Operating Margin",
          "optimal": ">=15%",
          "industry_average": "24%",
          "realtime_value": "60.38%",
          "importance": "Profit from core business before taxes."
        },
        {
          "name": "EPS YoY",
          "optimal": ">=15% annually",
          "industry_average": "14%",
          "realtime_value": "73.51%",
          "importance": "Shows how fast profits are growing."
        },
        {
          "name": "Revenue Growth YoY",
          "optimal": ">=15%",
          "industry_average": "15%",
          "realtime_value": "114.20%",
          "importance": "Shows top-line revenue expansion year over year."
        },
        {
          "name": "Revenue Growth 3–5 Year CAGR",
          "optimal": ">=10%",
          "industry_average": "18%",
          "realtime_value": "69.21%",
          "importance": "Average revenue growth over the past 3–5 years."
        },
        {
          "name": "FCF Margin",
          "optimal": ">=10%",
          "industry_average": "20%",
          "realtime_value": "44.49%",
          "importance": "Measures how much revenue turns into cash."
        }
      ]
    },
    {
      "type": "value",
      "score": 5,
      "max_score": 10,
      "ratios": [
        {
          "name": "Beta",
          "optimal": "<1.0 low risk, >1.0 volatile",
          "industry_average": "1.35",
          "realtime_value": "2.28",
          "importance": "Measures volatility vs overall market."
        },
        {
          "name": "P/E",
          "optimal": ">=20-50 (sector), <sector undervalued",
          "industry_average": "31.0",
          "realtime_value": "40.73",
          "importance": "How much investors pay for $1 of earnings."
        },
        {
          "name": "Forward P/E",
          "optimal": "<industry avg, >=10-20 stability",
          "industry_average": "24.0",
          "realtime_value": "17.93",
          "importance": "Shows if the stock is cheap or expensive based on future earnings."
        },
        {
          "name": "PEG",
          "optimal": "<1.0",
          "industry_average": "1.8",
          "realtime_value": "0.46",
          "importance": "PEG <1.0 suggests undervalued relative to growth prospects."
        },
        {
          "name": "P/B",
          "optimal": "<1.5 stability, <1.0 undervaluation",
          "industry_average": "6.8",
          "realtime_value": "30.85",
          "importance": "Compares market value to net assets."
        },
        {
          "name": "P/S",
          "optimal": "<2.0, <1.0 cheap",
          "industry_average": "8.5",
          "realtime_value": "22.47",
          "importance": "Compares price to annual revenue."
        },
        {
          "name": "EV/EBITDA",
          "optimal": "<10 signals undervaluation",
          "industry_average": "20.5",
          "realtime_value": "36.03",
          "importance": "Compares total company value to operating cash earnings."
        },
        {
          "name": "Debt/EQ",
          "optimal": "<1.0 for value stocks",
          "industry_average": "0.42",
          "realtime_value": "0.07",
          "importance": "Shows reliance on debt vs own capital."
        },
        {
          "name": "LT Debt/EQ",
          "optimal": "<1.0 most sectors, <0.5 stable for dividend stocks",
          "industry_average": "0.28",
          "realtime_value": "0.06",
          "importance": "Indicates financial stability and how safely dividends can be maintained."
        },
        {
          "name": "Current Ratio",
          "optimal": ">1.5 comfortable, <1.0 liquidity issues",
          "industry_average": "2.6",
          "realtime_value": "3.91",
          "importance": "Ability to cover ST liabilities with ST assets."
        }
      ]
    }
  ],
  "total_score": 11,
  "total_max": 16,
  "percentage": 68.8
}
```

**LLM-rendered output** (when an LLM client receives the above JSON, it renders it as):

> **NVDA  $199.64  (growth, value)**
>
> **growth: 6 / 6**
>
> | Ratio | Optimal Value | Industry Average | Real-Time Value | Importance |
> |---|---|---|---|---|
> | Gross Margin | >=40% | 53% | 71.07% | % of revenue left after production costs. |
> | Operating Margin | >=15% | 24% | 60.38% | Profit from core business before taxes. |
> | EPS YoY | >=15% annually | 14% | 73.51% | Shows how fast profits are growing. |
> | Revenue Growth YoY | >=15% | 15% | 114.20% | Shows top-line revenue expansion year over year. |
> | Revenue Growth 3–5 Year CAGR | >=10% | 18% | 69.21% | Average revenue growth over the past 3–5 years. |
> | FCF Margin | >=10% | 20% | 44.49% | Measures how much revenue turns into cash. |
>
> **value: 5 / 10**
>
> | Ratio | Optimal Value | Industry Average | Real-Time Value | Importance |
> |---|---|---|---|---|
> | Beta | <1.0 low risk, >1.0 volatile | 1.35 | 2.28 | Measures volatility vs overall market. |
> | P/E | >=20-50 (sector), <sector undervalued | 31.0 | 40.73 | How much investors pay for $1 of earnings. |
> | Forward P/E | <industry avg, >=10-20 stability | 24.0 | 17.93 | Shows if stock is cheap or expensive based on future earnings. |
> | PEG | <1.0 | 1.8 | 0.46 | PEG <1.0 suggests undervalued relative to growth prospects. |
> | P/B | <1.5 stability, <1.0 undervaluation | 6.8 | 30.85 | Compares market value to net assets. |
> | P/S | <2.0, <1.0 cheap | 8.5 | 22.47 | Compares price to annual revenue. |
> | EV/EBITDA | <10 signals undervaluation | 20.5 | 36.03 | Compares total company value to operating cash earnings. |
> | Debt/EQ | <1.0 for value stocks | 0.42 | 0.07 | Shows reliance on debt vs own capital. |
> | LT Debt/EQ | <1.0 most sectors, <0.5 stable | 0.28 | 0.06 | Indicates financial stability. |
> | Current Ratio | >1.5 comfortable, <1.0 liquidity | 2.6 | 3.91 | Ability to cover ST liabilities with ST assets. |
>
> **Investment Score: 11 / 16 (68.8%)**
>
> NVDA crushes it on growth — perfect 6/6 with every metric well above industry averages. On the value side, it scores 5/10 — strong on debt metrics (Debt/EQ 0.07 vs 0.42 industry avg) and Forward P/E (17.93 vs 24.0), but the premium valuation shows in P/B, P/S, and EV/EBITDA being well above industry norms. Classic high-growth stock profile.

**`get_ratio_definitions` tool** — `get_ratio_definitions(stock_type="div")`:

```json
{
  "stock_type": "div",
  "ratios": [
    {
      "name": "Dividend Yield",
      "optimal": ">=2-5%",
      "importance": "% of share price paid as dividends yearly.",
      "format_type": "percentage",
      "compare_direction": "higher_is_better"
    },
    {
      "name": "Dividend Payout",
      "optimal": ">=30-70%",
      "importance": "% of earnings paid as dividend.",
      "format_type": "percentage",
      "compare_direction": "higher_is_better"
    },
    {
      "name": "Dividend Growth Rate (3-5 yr)",
      "optimal": ">=5-10% per year",
      "importance": "Shows the company can reliably increase payouts over time.",
      "format_type": "percentage",
      "compare_direction": "higher_is_better"
    }
  ]
}
```

**Error response** — `stock_screener(ticker="AAPL", stock_type="invalid")`:

```json
{
  "error": "Unknown stock type 'invalid'. Valid types: ['div', 'growth', 'value']"
}
```

### Requirement 26: Calculated Ratios

**User Story:** As a user, I want the growth screening to include FCF Margin as a calculated ratio derived from other finviz values, so that I can assess a company's cash generation efficiency even when the metric is not directly available on finviz.

#### Acceptance Criteria

1. THE RatioInfo dataclass SHALL support a new optional field `source_labels` (a list of finviz label strings) to identify the finviz values needed to compute a Calculated_Ratio, and a new optional field `calculation` (a string identifier) to specify the formula to apply.
2. WHEN a RatioInfo has a non-empty `source_labels` and `calculation` field, THE HtmlParser SHALL treat it as a Calculated_Ratio and extract the values for each source label rather than looking up a single `finviz_label`.
3. THE FCF Margin ratio SHALL have `source_labels=["P/S", "P/FCF"]` and `calculation="ps_div_pfcf_times_100"`, indicating the formula: FCF Margin = (P/S ÷ P/FCF) × 100.
4. WHEN computing FCF Margin, THE HtmlParser SHALL extract the numeric values for "P/S" and "P/FCF" from the Finviz_Page, divide P/S by P/FCF, multiply by 100, and return the result formatted as a percentage string (e.g., "26.82%").
5. IF either source value ("P/S" or "P/FCF") is missing or non-numeric on the Finviz_Page, THEN THE HtmlParser SHALL return "N/A" for the FCF Margin ratio.
6. IF the "P/FCF" value is zero or negative (indicating no free cash flow), THEN THE HtmlParser SHALL return "N/A" for the FCF Margin ratio rather than producing an invalid result.
7. THE `finviz_label` field on a Calculated_Ratio SHALL be set to an empty string `""` since it is not used for direct lookup.
8. THE Revenue Growth YoY ratio SHALL use the finviz label `"Sales Y/Y TTM"` and display as "Revenue Growth YoY" in the results table.
9. THE Revenue Growth 3–5 Year CAGR ratio SHALL use the finviz label `"Sales past 3/5Y"` and display as "Revenue Growth 3–5 Year CAGR" in the results table.
10. WHEN the finviz field "Sales past 3/5Y" contains a single percentage value, THE HtmlParser SHALL use that value directly as the Revenue Growth 3–5 Year CAGR.
11. WHEN the finviz field "Sales past 3/5Y" for Revenue Growth 3–5 Year CAGR contains multiple values separated by "/" (e.g., "41.55%/51.61%"), THE Results_Table SHALL display the full unmodified value, but THE Scorer SHALL use only the first value (the 3-year CAGR) for investment score comparison. This slash-split behavior SHALL apply exclusively to the Revenue Growth 3–5 Year CAGR ratio and SHALL NOT affect scoring for any other ratio.

### Requirement 27: Revenue Growth 3–5 Year CAGR Value Parsing

**User Story:** As a user, I want the Revenue Growth 3–5 Year CAGR to display both the 3-year and 5-year values clearly separated, and use only the 3-year value for scoring, so that the output is readable and the score is based on the shorter-term growth metric.

#### Acceptance Criteria

1. WHEN the finviz "Sales past 3/5Y" cell contains two concatenated percentage values (e.g., "41.55%51.61%"), THE HtmlParser SHALL reformat the value to "{first_value} / {second_value}" (e.g., "41.55% / 51.61%") before storing it in the results dictionary.
2. THE reformatted value "41.55% / 51.61%" SHALL be displayed in the Real-Time Value column of the results table.
3. WHEN scoring the "Revenue Growth 3–5 Year CAGR" ratio, THE Scorer SHALL split the value on " / " and use only the first segment (the 3-year CAGR) for comparison against the industry average.
4. WHEN the finviz "Sales past 3/5Y" cell contains only a single percentage value, THE HtmlParser SHALL store it unchanged.
5. THE regex pattern used to detect the two-value concatenation SHALL be `r"(-?[\d.]+%)(-?[\d.]+%)"`.
