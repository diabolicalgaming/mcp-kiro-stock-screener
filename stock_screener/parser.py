"""HTML parser for extracting financial ratios from finviz pages."""

from __future__ import annotations

import re
from collections.abc import Callable

from bs4 import Tag
from bs4 import NavigableString
from bs4 import BeautifulSoup

from stock_screener.ratios import RatioInfo


_CALCULATIONS: dict[str, Callable[[list[float]], float | None]] = {
    "inverse_pe_times_100": lambda vals: (
        (1.0 / vals[0]) * 100.0 if vals[0] > 0 else None
    ),
    "ps_div_pfcf_times_100": lambda vals: (
        (vals[0] / vals[1]) * 100.0 if len(vals) > 1 and vals[1] > 0 else None
    ),
}


class HtmlParser:
    """Parses finviz HTML to extract ratio values and stock price."""

    def __init__(self, html: str) -> None:
        self._soup: BeautifulSoup = BeautifulSoup(html, "html.parser")

    def _extract_source_values(
        self,
        cells: list[Tag],
        source_labels: list[str],
    ) -> list[float] | None:
        """
        Extract numeric values for the given source labels from the
        snapshot table cells.

        Returns a list of floats in the same order as source_labels,
        or None if any label is missing or non-numeric.
        """
        label_values: dict[str, str] = {}
        for i in range(0, len(cells) - 1, 2):
            label_text: str = cells[i].get_text(strip=True)
            if label_text in source_labels:
                label_values[label_text] = cells[i + 1].get_text(strip=True)

        values: list[float] = []
        for label in source_labels:
            raw: str | None = label_values.get(label)
            if raw is None:
                return None
            tokens: list[str] = re.findall(r"-?[\d.]+", raw)
            if not tokens:
                return None
            try:
                values.append(float(tokens[0]))
            except ValueError:
                return None
        return values

    def _compute_calculated_ratio(
        self,
        ratio: RatioInfo,
        cells: list[Tag],
    ) -> str:
        """
        Compute a calculated ratio using the _CALCULATIONS dispatch.

        Returns a formatted percentage string (e.g., "3.29%") or "N/A".
        """
        try:
            calc_fn: Callable[[list[float]], float | None] | None = (
                _CALCULATIONS.get(ratio.calculation)
            )
            if calc_fn is None:
                return "N/A"

            source_values: list[float] | None = (
                self._extract_source_values(cells, ratio.source_labels)
            )
            if source_values is None:
                return "N/A"

            result: float | None = calc_fn(source_values)
            if result is None:
                return "N/A"

            return f"{result:.2f}%"
        except (ValueError, ZeroDivisionError, IndexError, TypeError):
            return "N/A"

    def parse_ratios(self, ratio_set: list[RatioInfo]) -> dict[str, str]:
        """
        Extract values for each ratio in ratio_set from the HTML.

        Returns a dict mapping ratio name -> value string.
        Missing ratios get value "N/A".

        For ratios with a non-empty finviz_label: looks up the value
        directly from the HTML snapshot table.

        For ratios with an empty finviz_label and non-empty calculation:
        computes the value using the _CALCULATIONS dispatch dict.
        """
        results: dict[str, str] = {}
        label_to_name: dict[str, str] = {
            ratio.finviz_label: ratio.name
            for ratio in ratio_set
            if ratio.finviz_label != ""
        }

        try:
            snapshot_result: Tag | NavigableString | None = self._soup.find(
                "table", class_="snapshot-table2"
            )
            snapshot_table: Tag | None = (
                snapshot_result if isinstance(snapshot_result, Tag) else None
            )
            if snapshot_table is None:
                return {ratio.name: "N/A" for ratio in ratio_set}

            cells: list[Tag] = snapshot_table.find_all("td")
            for i in range(0, len(cells) - 1, 2):
                label_text: str = cells[i].get_text(strip=True)
                if label_text in label_to_name:
                    value_text: str = cells[i + 1].get_text(strip=True)
                    if label_text == "Sales past 3/5Y":
                        cagr_match = re.match(
                            r"(-?[\d.]+%)(-?[\d.]+%)", value_text
                        )
                        if cagr_match:
                            value_text = (
                                f"{cagr_match.group(1)} / "
                                f"{cagr_match.group(2)}"
                            )
                    results[label_to_name[label_text]] = value_text

            # Handle calculated ratios (empty finviz_label, non-empty calculation)
            for ratio in ratio_set:
                if ratio.finviz_label == "" and ratio.calculation:
                    results[ratio.name] = self._compute_calculated_ratio(
                        ratio, cells
                    )

        except (AttributeError, IndexError, TypeError):
            pass

        for ratio in ratio_set:
            if ratio.name not in results:
                results[ratio.name] = "N/A"

        return results

    def parse_price(self) -> str:
        """
        Extract the current stock price from the HTML.

        Returns "N/A" if price cannot be found.
        """
        try:
            price_result: Tag | NavigableString | None = self._soup.find(
                "strong", class_="quote-price_wrapper_price"
            )
            price_tag: Tag | None = (
                price_result if isinstance(price_result, Tag) else None
            )
            if price_tag is not None:
                price_text: str = price_tag.get_text(strip=True)
                return price_text
            return "N/A"
        except (AttributeError, TypeError):
            return "N/A"

    def parse_sector_industry(self) -> tuple[str, str]:
        """
        Extract sector and industry from the quote-links div.

        Returns a tuple of (sector, industry).
        Returns ("Unknown", "Unknown") if not found.
        """
        try:
            div_result: Tag | NavigableString | None = self._soup.find(
                "div", class_="quote-links whitespace-nowrap gap-8"
            )
            div_tag: Tag | None = (
                div_result if isinstance(div_result, Tag) else None
            )
            if div_tag is None:
                return ("Unknown", "Unknown")

            links: list[Tag] = div_tag.find_all("a")
            sector: str = (
                links[0].get_text(strip=True) if len(links) > 0 else "Unknown"
            )
            industry: str = (
                links[1].get_text(strip=True) if len(links) > 1 else "Unknown"
            )
            return (sector, industry)
        except (AttributeError, IndexError, TypeError):
            return ("Unknown", "Unknown")
