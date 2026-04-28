# mcp-kiro-stock-screener

This project converts my kiro-stock-screener project to an MCP server.

---

## Prerequisites

### Supported Operating Systems

| OS      | Status    | Notes                                      |
|---------|-----------|--------------------------------------------|
| macOS   | Supported | Primary development platform               |
| Linux   | Supported | Any modern distribution with Chrome/Chromium |
| Windows | Supported | Requires Chrome and Python on PATH          |

### Required Software

1. **Python 3.11+** — install via [pyenv](https://github.com/pyenv/pyenv) (recommended) or your system package manager.

   ```bash
   pyenv install 3.11.1
   pyenv local 3.11.1
   ```

2. **Google Chrome** — required by Selenium for headless web scraping. ChromeDriver is managed automatically by `webdriver-manager`.

3. **An OpenAI API key** — used to fetch industry-average data. Set it as an environment variable or pass it via `--api-key`.

   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

### Python Libraries

Install all dependencies with pip:

```bash
pip install selenium beautifulsoup4 pandas tabulate rich openai fastmcp filelock webdriver-manager
```

| Package             | Purpose                                                  |
|---------------------|----------------------------------------------------------|
| `selenium`          | Headless Chrome scraping of finviz.com                   |
| `beautifulsoup4`    | HTML parsing to extract financial ratios                 |
| `pandas`            | DataFrame construction for ratio tables                  |
| `tabulate`          | Smart column alignment for terminal table output         |
| `rich`              | Colored and styled terminal output                       |
| `openai`            | OpenAI API client for industry-average lookups           |
| `fastmcp`           | MCP server framework for tool/prompt exposure            |
| `filelock`          | Cross-platform file locking for concurrent cache access  |
| `webdriver-manager` | Automatic ChromeDriver installation and management       |

---

## User Manual

### Using as a Python CLI Application

Run the screener from the project root:

```bash
python stock_screener/main.py <TICKER> <STOCK_TYPE> [OPTIONS]
```

#### Arguments

| Argument       | Required | Description                                                        |
|----------------|----------|--------------------------------------------------------------------|
| `ticker`       | Yes      | Stock ticker symbol (e.g. `AAPL`, `MSFT`)                         |
| `stock_type`   | Yes      | One or more types: `div`, `growth`, `value` (comma-separated)      |
| `--api-key`    | No       | OpenAI API key (falls back to `OPENAI_API_KEY` env var)            |
| `--no-cache`   | No       | Disable cache entirely — always call the API                       |
| `--refresh`    | No       | Ignore cached data but write fresh results to cache                |

> `--no-cache` and `--refresh` are mutually exclusive.

#### Examples

Screen a single stock type:

```bash
python stock_screener/main.py AAPL div
```

Screen multiple stock types at once:

```bash
python stock_screener/main.py MSFT growth,value
```

Bypass the cache entirely (no reads or writes):

```bash
python stock_screener/main.py AAPL div --no-cache
```

Force a fresh API call and update the cache:

```bash
python stock_screener/main.py GOOG div,growth,value --refresh
```

Pass an API key directly:

```bash
python stock_screener/main.py AAPL value --api-key sk-your-key-here
```

#### Example Output — Single Stock Type

```
╭─────────────────────────────────────────────────────────────────────────────╮
│                           AAPL  $270.77  (div)                              │
╰─────────────────────────────────────────────────────────────────────────────╯
div: 0 / 3

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Ratio                         ┃ Optimal Value    ┃ Industry Average ┃ Real-Time Value ┃ Importance                                                 ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Dividend Yield                │ >=2-5%           │ 1.2%             │ 1.04 (0.38%)    │ % of share price paid as dividends yearly.                 │
├───────────────────────────────┼──────────────────┼──────────────────┼─────────────────┼────────────────────────────────────────────────────────────┤
│ Dividend Payout               │ >=30-70%         │ 18%              │ 13.66%          │ % of earnings paid as dividend.                            │
├───────────────────────────────┼──────────────────┼──────────────────┼─────────────────┼────────────────────────────────────────────────────────────┤
│ Dividend Growth Rate (3-5 yr) │ >=5-10% per year │ 8%               │ 4.26% 4.98%     │ Shows the company can reliably increase payouts over time. │
└───────────────────────────────┴──────────────────┴──────────────────┴─────────────────┴────────────────────────────────────────────────────────────┘
╭─────────────────────────────────────────────────────────────────────────────╮
│                      Investment Score: 0 / 3 (0.0%)                         │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Example Output — Multiple Stock Types

```
╭─────────────────────────────────────────────────────────────────────────────╮
│                      AAPL  $270.77  (growth, value)                         │
╰─────────────────────────────────────────────────────────────────────────────╯
growth: 6 / 6

┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Ratio            ┃ Optimal Value  ┃ Industry Average ┃ Real-Time Value ┃ Importance                                              ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Gross Margin     │ >=40%          │ 38%              │ 47.33%          │ % of revenue left after production costs.               │
├──────────────────┼────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────┤
│ Operating Margin │ >=15%          │ 12%              │ 32.38%          │ Profit from core business before taxes.                 │
├──────────────────┼────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────┤
│ ROE              │ >=15%          │ 18%              │ 152.02%         │ Profitability of shareholder's capital.                 │
├──────────────────┼────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────┤
│ ROA              │ >=5%           │ 8%               │ 32.56%          │ Profitability using all company assets.                 │
├──────────────────┼────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────┤
│ EPS YoY          │ >=15% annually │ 10%              │ 14.06%          │ Shows how fast profits are growing.                     │
├──────────────────┼────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────┤
│ EPS YoY (TTM)    │ >=10%          │ 10%              │ 25.58%          │ Measures if the company can actually grow its earnings. │
└──────────────────┴────────────────┴──────────────────┴─────────────────┴─────────────────────────────────────────────────────────┘
value: 1 / 10

┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Ratio         ┃ Optimal Value                                      ┃ Industry Average ┃ Real-Time Value ┃ Importance                                                      ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Beta          │ <1.0 low risk, >1.0 volatile                       │ 1.15             │ 1.06            │ Measures volatility vs overall market.                          │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ P/E           │ >=20-50 (sector), <sector undervalued              │ 28.0             │ 34.26           │ How much investors pay for $1 of earnings.                      │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ Forward P/E   │ <industry avg, >=10-20 stability                   │ 24.0             │ 28.94           │ Shows if the stock is cheap or expensive based on future        │
│               │                                                    │                  │                 │ earnings.                                                       │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ PEG           │ <1.0                                               │ 1.8              │ 2.50            │ PEG <1.0 suggests undervalued relative to growth prospects.     │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ P/B           │ <1.5 stability, <1.0 undervaluation                │ 6.5              │ 45.14           │ Compares market value to net assets.                            │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ P/S           │ <2.0, <1.0 cheap                                   │ 3.2              │ 9.13            │ Compares price to annual revenue.                               │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ EV/EBITDA     │ <10 signals undervaluation                         │ 18.0             │ 26.15           │ Compares total company value to operating cash earnings.        │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ Debt/EQ       │ <1.0 for value stocks                              │ 0.55             │ 1.03            │ Shows reliance on debt vs own capital.                          │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ LT Debt/EQ    │ <1.0 most sectors, <0.5 stable for dividend stocks │ 0.35             │ 0.87            │ Indicates financial stability and how safely dividends can be   │
│               │                                                    │                  │                 │ maintained.                                                     │
├───────────────┼────────────────────────────────────────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────┤
│ Current Ratio │ >1.5 comfortable, <1.0 liquidity issues            │ 1.8              │ 0.97            │ Ability to cover ST liabilities with ST assets.                 │
└───────────────┴────────────────────────────────────────────────────┴──────────────────┴─────────────────┴─────────────────────────────────────────────────────────────────┘
╭─────────────────────────────────────────────────────────────────────────────╮
│                     Investment Score: 7 / 16 (43.8%)                        │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Output Format

The CLI displays:
1. A banner header with the ticker, current price, and stock type(s).
2. For each stock type, a labeled score line followed by a table with columns: **Ratio**, **Optimal Value**, **Industry Average**, **Real-Time Value**, **Importance**.
3. A cumulative **Investment Score** banner with percentage.

#### Caching

Industry-average data is cached locally at `~/.stock_screener/cache.json` with a 7-day TTL. Use `--no-cache` to skip the cache entirely, or `--refresh` to force a fresh lookup while updating the cache for future runs.

---

### Using as an MCP Server

The application exposes the same functionality as an MCP server via [FastMCP](https://github.com/jlowin/fastmcp), making it available to any MCP-compatible client (e.g. Kiro, Claude Desktop).

#### Starting the Server

```bash
python stock_screener/mcp_server.py
```

#### Registering in Kiro

Add the following to your `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "stock-screener": {
      "command": "python",
      "args": ["stock_screener/mcp_server.py"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

#### Available Tools

**`stock_screener`** — Screen a stock by ticker and type(s).

| Parameter    | Type   | Default | Description                                              |
|--------------|--------|---------|----------------------------------------------------------|
| `ticker`     | string | —       | Stock ticker symbol (e.g. `AAPL`)                        |
| `stock_type` | string | —       | Comma-separated stock types: `div`, `growth`, `value`    |
| `api_key`    | string | `""`    | OpenAI API key (falls back to `OPENAI_API_KEY` env var)  |
| `no_cache`   | bool   | `false` | Disable cache entirely                                   |
| `refresh`    | bool   | `false` | Ignore cached data but update the cache                  |

Returns a structured JSON object with ticker info, per-type ratio tables with scores, and a cumulative investment score percentage.

**`get_ratio_definitions`** — Get the ratio definitions for a stock type.

| Parameter    | Type   | Description                          |
|--------------|--------|--------------------------------------|
| `stock_type` | string | One of: `div`, `growth`, `value`     |

Returns the list of ratios with their name, optimal value, importance, format type, and compare direction.

#### Available Prompts

**`screen_stock`** — Prompt template for screening one or more stocks with formatted table output.

| Parameter    | Type   | Description                                                    |
|--------------|--------|----------------------------------------------------------------|
| `ticker`     | string | One or more tickers, comma-separated (e.g. `AAPL,MSFT,GOOG`)  |
| `stock_type` | string | Comma-separated stock types: `div`, `growth`, `value`          |

Generates a prompt that instructs the LLM to call the `stock_screener` tool for each ticker and render results as formatted tables with scores, separated by horizontal rules for multiple tickers.
