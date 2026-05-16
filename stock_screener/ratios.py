"""Financial ratio definitions and configuration resolver."""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class RatioInfo:
    """Represents a single financial ratio with its metadata."""

    name: str
    finviz_label: str
    optimal: str
    importance: str
    format_type: str
    compare_direction: str
    source_labels: list[str] = field(default_factory=list)
    calculation: str = ""


class OptimalRange:
    """Parsed optimal range with operator and boundary values."""

    def __init__(
        self,
        operator: str,
        low: float,
        high: float | None,
    ) -> None:
        self.operator: str = operator
        self.low: float = low
        self.high: float | None = high

    def is_within(self, value: float) -> bool:
        """Return True if value satisfies the optimal condition."""
        if self.high is not None:
            return self.low <= value <= self.high
        if self.operator in (">=", ">"):
            return value >= self.low
        if self.operator in ("<=", "<"):
            return value < self.low
        return False


_RANGE_PATTERN: re.Pattern[str] = re.compile(
    r"([><]=?)\s*(-?[\d.]+)\s*(?:-\s*(-?[\d.]+))?"
)


def parse_optimal(optimal: str) -> OptimalRange | None:
    """Extract the first numeric threshold from an optimal string."""
    match: re.Match[str] | None = _RANGE_PATTERN.search(optimal)
    if match is None:
        return None
    try:
        operator: str = match.group(1)
        low: float = float(match.group(2))
        high: float | None = (
            float(match.group(3)) if match.group(3) else None
        )
        return OptimalRange(operator, low, high)
    except (ValueError, TypeError):
        return None


class RatioConfigResolver:  # pylint: disable=too-few-public-methods
    """Resolves the ratio set for a given stock type."""

    _RATIO_SETS: dict[str, list[RatioInfo]] = {
        "div": [
            RatioInfo(
                "Dividend Yield",
                "Dividend TTM",
                ">=2-5%",
                "% of share price paid as dividends yearly.",
                "percentage",
                "higher_is_better",
            ),
            RatioInfo(
                "Dividend Payout",
                "Payout",
                ">=30-70%",
                "% of earnings paid as dividend.",
                "percentage",
                "higher_is_better",
            ),
            RatioInfo(
                "Dividend Growth Rate (3-5 yr)",
                "Dividend Gr. 3/5Y",
                ">=5-10% per year",
                "Shows the company can reliably increase payouts over time.",
                "percentage",
                "higher_is_better",
            ),
        ],
        "growth": [
            RatioInfo(
                "Gross Margin",
                "Gross Margin",
                ">=40%",
                "% of revenue left after production costs.",
                "percentage",
                "higher_is_better",
            ),
            RatioInfo(
                "Operating Margin",
                "Oper. Margin",
                ">=15%",
                "Profit from core business before taxes.",
                "percentage",
                "higher_is_better",
            ),
            RatioInfo(
                "EPS YoY",
                "EPS this Y",
                ">=15% annually",
                "Shows how fast profits are growing.",
                "percentage",
                "higher_is_better",
            ),
            RatioInfo(
                "Revenue Growth YoY",
                "Sales Y/Y TTM",
                ">=15%",
                "Shows top-line revenue expansion year over year.",
                "percentage",
                "higher_is_better",
            ),
            RatioInfo(
                "Revenue Growth 3-5 Year CAGR",
                "Sales past 3/5Y",
                ">=10%",
                "Average revenue growth over the past 3-5 years.",
                "percentage",
                "higher_is_better",
            ),
            RatioInfo(
                "FCF Margin",
                "",
                ">=10%",
                "Measures how much revenue turns into cash.",
                "percentage",
                "higher_is_better",
                source_labels=["P/S", "P/FCF"],
                calculation="ps_div_pfcf_times_100",
            ),
        ],
        "value": [
            RatioInfo(
                "Beta",
                "Beta",
                "<1.0 low risk, >1.0 volatile",
                "Measures volatility vs overall market.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "Forward P/E",
                "Forward P/E",
                "<industry avg, >=10-20 stability",
                "Shows if the stock is cheap or expensive based on future earnings.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "PEG",
                "PEG",
                "<1.0",
                "PEG <1.0 suggests undervalued relative to growth prospects.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "EV/EBITDA",
                "EV/EBITDA",
                "<10 signals undervaluation",
                "Compares total company value to operating cash earnings.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "P/S",
                "P/S",
                "<2.0, <1.0 cheap",
                "Compares price to annual revenue.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "EV/Revenue",
                "EV/Sales",
                "<5.0, <3.0 cheap",
                "Measures how expensive the company is relative to its revenue.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "Earnings Yield",
                "",
                ">=5%",
                "Measures how much earnings you get for the stock price paid.",
                "percentage",
                "higher_is_better",
                source_labels=["P/E"],
                calculation="inverse_pe_times_100",
            ),
            RatioInfo(
                "Debt/EQ",
                "Debt/Eq",
                "<1.0 for value stocks",
                "Shows reliance on debt vs own capital.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "LT Debt/EQ",
                "LT Debt/Eq",
                "<1.0 most sectors, <0.5 stable for dividend stocks",
                "Indicates financial stability and how safely dividends can be maintained.",
                "multiple",
                "lower_is_better",
            ),
            RatioInfo(
                "Current Ratio",
                "Current Ratio",
                ">1.5 comfortable, <1.0 liquidity issues",
                "Ability to cover ST liabilities with ST assets.",
                "multiple",
                "higher_is_better",
            ),
        ],
    }

    def get_ratio_set(self, stock_type: str) -> list[RatioInfo]:
        """
        Return the list of RatioInfo for the given stock type.

        Raises ValueError for unknown stock type.
        """
        if stock_type not in self._RATIO_SETS:
            raise ValueError(
                f"Unknown stock type '{stock_type}'. "
                f"Valid types: {list(self._RATIO_SETS.keys())}"
            )
        return self._RATIO_SETS[stock_type]
