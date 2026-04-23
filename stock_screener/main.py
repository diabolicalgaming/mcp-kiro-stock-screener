"""Entry point for the Stock Screener CLI application."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so absolute imports resolve
# regardless of how this script is invoked.
_PROJECT_ROOT: str = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from stock_screener.app import StockScreenerApp  # noqa: E402  pylint: disable=wrong-import-position


def main() -> None:
    """Create and run the stock screener application."""
    app: StockScreenerApp = StockScreenerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
