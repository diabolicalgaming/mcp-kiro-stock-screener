"""Computes investment scores by comparing real-time values to industry averages."""

from __future__ import annotations

import re

from stock_screener.ratios import RatioInfo
from stock_screener.ratios import OptimalRange
from stock_screener.ratios import parse_optimal


class Scorer:
    """Computes investment scores by comparing real-time values to industry averages."""

    @staticmethod
    def _parse_numeric(value: str) -> float | None:
        """
        Parse a value string into a float, extracting the last numeric
        token to handle compound finviz formats.

        Handles:
        - Simple values: "62.63%", "1.5", "N/A"
        - Bracketed values: "4.23 (2.91%)" → extracts 2.91
        - Space-separated values: "5.04% 6.13%" → extracts 6.13

        Returns None for "N/A", "-", empty, or unparseable values.
        """
        stripped: str = value.strip()
        if stripped in ("N/A", "-", ""):
            return None
        tokens: list[str] = re.findall(r"-?[\d.]+", stripped)
        if not tokens:
            return None
        try:
            return float(tokens[-1])
        except ValueError:
            return None

    @staticmethod
    def _beats_average(
        realtime: float,
        industry_avg: float,
        compare_direction: str,
    ) -> bool:
        """
        Return True if the real-time value beats the industry average
        based on the compare_direction.

        - "higher_is_better": realtime > industry_avg
        - "lower_is_better": realtime < industry_avg
        """
        if compare_direction == "higher_is_better":
            return realtime > industry_avg
        if compare_direction == "lower_is_better":
            return realtime < industry_avg
        return False

    def score_ratios(
        self,
        ratio_set: list[RatioInfo],
        values: dict[str, str],
        industry_averages: dict[str, str],
        stock_type: str = "",
    ) -> tuple[int, int]:
        """
        Compute the investment score for a set of ratios.

        For growth and value stock types:
        - Score a point if the real-time value beats the industry average.

        For dividend stock type:
        - Score a point only if the real-time value beats the industry
          average AND falls within the optimal value range.

        Returns (score, max_score) where max_score = len(ratio_set).
        """
        score: int = 0
        for ratio in ratio_set:
            raw_realtime: str = values.get(ratio.name, "N/A")
            if (
                ratio.name == "Revenue Growth 3\u20135 Year CAGR"
                and "/" in raw_realtime
            ):
                raw_realtime = raw_realtime.split("/")[0]
            realtime: float | None = self._parse_numeric(raw_realtime)
            industry_avg: float | None = self._parse_numeric(
                industry_averages.get(ratio.name, "N/A")
            )
            if realtime is None or industry_avg is None:
                continue
            if not self._beats_average(
                realtime, industry_avg, ratio.compare_direction
            ):
                continue
            if stock_type == "div":
                optimal_range: OptimalRange | None = (
                    parse_optimal(ratio.optimal)
                )
                if optimal_range is None or not optimal_range.is_within(realtime):
                    continue
            score += 1
        return (score, len(ratio_set))
