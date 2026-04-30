"""Command-line argument parsing for the Stock Screener CLI."""

from __future__ import annotations

import re
import os
import sys
import argparse


class ArgumentParser:  # pylint: disable=too-few-public-methods
    """Parses and validates CLI arguments for the stock screener."""

    VALID_STOCK_TYPES: list[str] = ["div", "growth", "value"]
    TICKER_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z]+(-[a-zA-Z]+)?$")

    def __init__(self, argv: list[str] | None = None) -> None:
        self._argv: list[str] | None = argv
        self._parser: argparse.ArgumentParser = self._build_parser()

    @staticmethod
    def _validate_ticker(value: str) -> str:
        """Validate and normalize a single ticker symbol.

        Enforces two checks in order:
        1. Comma check — rejects multiple comma-separated tickers.
        2. Format check — validates against TICKER_PATTERN regex.

        Returns the uppercase ticker on success.
        Raises argparse.ArgumentTypeError on failure.
        """
        if "," in value:
            raise argparse.ArgumentTypeError(
                "Only one ticker is allowed. "
                "Use the MCP server for multiple tickers."
            )

        ticker: str = value.strip().upper()

        if not ArgumentParser.TICKER_PATTERN.match(ticker):
            raise argparse.ArgumentTypeError(
                f"Invalid ticker '{value}'. Ticker must be alphabetic, "
                "optionally with a single hyphen for share classes "
                "(e.g., BRK-B)."
            )

        return ticker

    def _build_parser(self) -> argparse.ArgumentParser:
        """Build the argparse parser with ticker and stock_type arguments."""
        parser: argparse.ArgumentParser = argparse.ArgumentParser(
            description="Screen stocks by financial ratios.",
        )
        parser.add_argument(
            "ticker",
            type=self._validate_ticker,
            help="Single stock ticker symbol (e.g. AAPL, MSFT, BRK-B).",
        )
        parser.add_argument(
            "stock_type",
            type=str,
            help="Stock type(s): div, growth, value (comma-separated for multiple).",
        )
        parser.add_argument(
            "--api-key",
            type=str,
            default=None,
            help="OpenAI API key (falls back to OPENAI_API_KEY env var).",
        )
        cache_group: argparse._MutuallyExclusiveGroup = (
            parser.add_mutually_exclusive_group()
        )
        cache_group.add_argument(
            "--no-cache",
            action="store_true",
            default=False,
            help="Disable cache entirely — always call the API.",
        )
        cache_group.add_argument(
            "--refresh",
            action="store_true",
            default=False,
            help="Force refresh — ignore cached data and update the cache.",
        )
        return parser

    def _parse_stock_types(self, raw: str) -> list[str]:
        """Split comma-separated stock types, deduplicate, and validate.

        Returns a list of unique, validated stock type strings.
        Prints error to stderr and calls sys.exit(1) if any type is invalid.
        """
        parts: list[str] = [part.strip() for part in raw.split(",")]
        unique: list[str] = list(dict.fromkeys(parts))

        for stock_type in unique:
            if stock_type not in self.VALID_STOCK_TYPES:
                self._parser.print_usage(sys.stderr)
                print(
                    f"error: Invalid stock type '{stock_type}'. "
                    f"Valid types: {', '.join(self.VALID_STOCK_TYPES)}",
                    file=sys.stderr,
                )
                sys.exit(1)

        return unique

    def parse(self) -> tuple[str, list[str], str, bool, bool]:
        """Parse arguments and return (ticker, stock_types, api_key, no_cache, refresh).

        stock_types is a list[str] — always at least one element.
        Reads --api-key from CLI arg first, falls back to OPENAI_API_KEY env var.
        Prints error to stderr and raises SystemExit if no API key is found.

        The ticker is already validated and uppercased by _validate_ticker
        at the argparse type level. The comma check below is a
        belt-and-suspenders safety net.
        """
        try:
            args: argparse.Namespace = self._parser.parse_args(self._argv)
        except SystemExit:
            sys.exit(1)

        stock_types: list[str] = self._parse_stock_types(args.stock_type)
        ticker: str = args.ticker

        if "," in ticker:
            print(
                "error: Only one ticker is allowed. "
                "Use the MCP server for multiple tickers.",
                file=sys.stderr,
            )
            sys.exit(1)

        api_key: str | None = args.api_key
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        if api_key is None:
            print(
                "error: No API key provided. Use --api-key or set "
                "the OPENAI_API_KEY environment variable.",
                file=sys.stderr,
            )
            sys.exit(1)

        no_cache: bool = args.no_cache
        refresh: bool = args.refresh

        return ticker, stock_types, api_key, no_cache, refresh
