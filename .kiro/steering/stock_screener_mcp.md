# Stock Screener MCP

* The application can also be used as a MCP server that provides the exact same functionality as the Python application.
* When used as a MCP server returns the exact same table for each stock ticker, displays the scores for each stock stype, and produces the results of the scoring system just like the Python application does. Each output for a stock ticker produced by the MCP server should be a separated output with a horizontal rule (---). This is as described by the function ```screen_stock()``` which is exposed using the mcp.propmt() decorator.