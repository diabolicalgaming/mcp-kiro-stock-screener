# Stock Screener MCP

* The application can also be used as a MCP server that provides the exact same functionality as the Python application.
* When used as a MCP server returns the exact same table for each stock ticker, displays the scores for each stock stype, and produces the results of the scoring system just like the Python application does. Each output for a stock ticker produced by the MCP server should be a separated output with a horizontal rule (---). This is as described by the function ```screen_stock()``` which is exposed using the mcp.propmt() decorator. The investement score should always be displayed after the table has been generated but before the separated horizontal rule (---).
* The multi-ticker prompt (`_build_multi_ticker_prompt()`) uses few-shot prompting with concrete examples (NVDA and NFLX) to enforce that each stock type is rendered as its own separate table with its own header row. This prevents LLMs from merging ratios from different stock types into a single combined table.
* Each few-shot example demonstrates: a banner header, then for each stock type a label line with score followed by a complete markdown table, and finally the Investment Score before the horizontal rule separator.
* Each ratio row in the MCP output MUST include a ✅ or ❌ indicator appended to the Real-Time Value, determined by the investment score algorithm in `Scorer`:
  - For **growth** and **value** stock types: ✅ if the real-time value beats the industry average based on `compare_direction` (`higher_is_better`: realtime > industry_avg; `lower_is_better`: realtime < industry_avg). ❌ otherwise.
  - For **dividend** stock type: ✅ only if the real-time value beats the industry average AND falls within the optimal value range. ❌ otherwise.
  - If either value is N/A or unparseable, the ratio does not score a point → ❌.
  - The total score per stock type equals the count of ✅ indicators in that table.
