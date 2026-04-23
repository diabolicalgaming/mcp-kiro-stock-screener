"""Table rendering for stock ratio data using Rich and tabulate."""

from __future__ import annotations

import re

import pandas as pd

from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.console import Console

from stock_screener.ratios import RatioInfo
from stock_screener.ratios import OptimalRange
from stock_screener.ratios import parse_optimal


class TableRenderer:
    """Renders stock ratio data as a styled terminal table."""

    _VALUE_TOKEN: re.Pattern[str] = re.compile(
        r"-?[\d.]+%?"
    )

    def __init__(self) -> None:
        self._console: Console = Console()

    @classmethod
    def _styled_optimal(cls, optimal: str) -> Text:
        """Return a Text with only numeric values (and %) in bright_blue."""
        result: Text = Text()
        last_end: int = 0
        for match in cls._VALUE_TOKEN.finditer(optimal):
            if match.start() > last_end:
                result.append(optimal[last_end:match.start()])
            result.append(match.group(), style="cyan")
            last_end = match.end()
        if last_end < len(optimal):
            result.append(optimal[last_end:])
        return result

    @staticmethod
    def _parse_realtime(value: str) -> float | None:
        """Parse a real-time value string into a float."""
        cleaned: str = value.strip().replace("%", "").replace(",", "")
        if cleaned in ("N/A", "-", ""):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _is_negative(value: str) -> bool:
        """Return True if the real-time value is negative."""
        cleaned: str = value.strip().replace("%", "").replace(",", "")
        try:
            return float(cleaned) < 0
        except ValueError:
            return False

    def _realtime_style(
        self,
        realtime_str: str,
        optimal_str: str,
    ) -> str:
        """Determine the Rich style for a real-time value cell."""
        if self._is_negative(realtime_str):
            return "red"
        parsed_range: OptimalRange | None = parse_optimal(optimal_str)
        parsed_value: float | None = self._parse_realtime(realtime_str)
        if parsed_range is not None and parsed_value is not None:
            if parsed_range.is_within(parsed_value):
                return "bright_green"
        return "default"

    def build_dataframe(
        self,
        ratio_set: list[RatioInfo],
        values: dict[str, str],
        industry_averages: dict[str, str],
    ) -> pd.DataFrame:
        """
        Build a Pandas DataFrame with five columns:
        Ratio, Optimal Value, Industry Average, Real-Time Value, Importance.
        """
        try:
            rows: list[dict[str, str]] = [
                {
                    "Ratio": ratio.name,
                    "Optimal Value": ratio.optimal,
                    "Industry Average": industry_averages.get(ratio.name, "N/A"),
                    "Real-Time Value": values.get(ratio.name, "N/A"),
                    "Importance": ratio.importance,
                }
                for ratio in ratio_set
            ]
            dataframe: pd.DataFrame = pd.DataFrame(rows)
        except (KeyError, ValueError, TypeError) as exc:
            self._console.print(
                f"[red]Error building dataframe: {exc}[/red]"
            )
            dataframe = pd.DataFrame(
                columns=[
                    "Ratio",
                    "Optimal Value",
                    "Industry Average",
                    "Real-Time Value",
                    "Importance",
                ]
            )
        return dataframe

    def render_header(
        self,
        ticker: str,
        price: str,
        stock_types: list[str],
    ) -> None:
        """
        Print a centered banner header using a Rich Panel.

        Format: <Ticker>  $<Price>  (<type1>, <type2>, ...)
        - Ticker in bright_blue
        - Price in bright_green
        - Stock types joined with ", " in default color

        Called exactly once per run, before any ratio tables.
        """
        try:
            types_display: str = ", ".join(stock_types)
            header_text: Text = Text(justify="center")
            header_text.append(ticker, style="bright_blue")
            header_text.append("  ")
            header_text.append(f"${price}", style="bright_green")
            header_text.append(f"  ({types_display})")
            panel: Panel = Panel(
                header_text,
                border_style="bright_blue",
                expand=True,
            )
            self._console.print(panel)
        except (ValueError, TypeError) as exc:
            self._console.print(
                f"[red]Error rendering header: {exc}[/red]"
            )

    def render_stock_type_label(
        self,
        stock_type: str,
        score: int,
        max_score: int,
    ) -> None:
        """
        Print the stock type label with score in styled colors.

        Format: {stock_type}: {score} / {max_score}
        - stock_type and colon in cyan
        - score and max_score in bright_magenta
        - "/" in white (default)

        Called once before each ratio table.
        """
        label: Text = Text()
        label.append(f"{stock_type}: ", style="cyan")
        label.append(str(score), style="bright_magenta")
        label.append(" / ")
        label.append(str(max_score), style="bright_magenta")
        self._console.print(label)
        self._console.print()

    def render_score_banner(
        self,
        total_score: int,
        total_max: int,
    ) -> None:
        """
        Render the cumulative Investment Score banner as a Rich Panel.

        Format: Investment Score: {total_score} / {total_max} ({percentage:.1f}%)
        - Banner border in bright_blue
        - Score numbers in bright_magenta
        - Percentage color: green (>70%), yellow (50-70%), red (<50%)

        Called once after all stock type tables have been rendered.
        """
        percentage: float = (
            (total_score / total_max * 100.0) if total_max > 0 else 0.0
        )
        if percentage > 70:
            pct_color: str = "green"
        elif percentage >= 50:
            pct_color = "yellow"
        else:
            pct_color = "red"

        banner_text: Text = Text(justify="center")
        banner_text.append("Investment Score: ")
        banner_text.append(str(total_score), style="bright_magenta")
        banner_text.append(" / ")
        banner_text.append(str(total_max), style="bright_magenta")
        banner_text.append(" (")
        banner_text.append(f"{percentage:.1f}%", style=pct_color)
        banner_text.append(")")

        panel: Panel = Panel(
            banner_text,
            border_style="bright_blue",
            expand=True,
        )
        self._console.print(panel)

    def render_table(self, dataframe: pd.DataFrame) -> None:
        """
        Render the DataFrame as a Rich Table with conditional coloring
        on both the Real-Time Value and Industry Average columns.
        """
        try:
            table: Table = Table(
                show_header=True,
                header_style="bold",
                show_lines=True,
            )
            table.add_column("Ratio")
            table.add_column("Optimal Value")
            table.add_column("Industry Average")
            table.add_column("Real-Time Value")
            table.add_column("Importance")

            for _, row in dataframe.iterrows():
                optimal_val: str = str(row["Optimal Value"])
                realtime_val: str = str(row["Real-Time Value"])
                industry_val: str = str(row["Industry Average"])
                rt_style: str = self._realtime_style(
                    realtime_val, optimal_val
                )
                ia_style: str = self._realtime_style(
                    industry_val, optimal_val
                )
                table.add_row(
                    str(row["Ratio"]),
                    self._styled_optimal(optimal_val),
                    Text(industry_val, style=ia_style),
                    Text(realtime_val, style=rt_style),
                    str(row["Importance"]),
                )

            self._console.print(table)
        except (ValueError, TypeError) as exc:
            self._console.print(
                f"[red]Error rendering table: {exc}[/red]"
            )
