"""HTML parser for extracting financial ratios from finviz pages."""

from __future__ import annotations

import re

from bs4 import Tag
from bs4 import NavigableString
from bs4 import BeautifulSoup

from stock_screener.ratios import RatioInfo


class HtmlParser:
    """Parses finviz HTML to extract ratio values and stock price."""

    def __init__(self, html: str) -> None:
        self._soup: BeautifulSoup = BeautifulSoup(html, "html.parser")

    def _compute_fcf_margin(self, cells: list[Tag]) -> str:
        """
        Compute FCF Margin = (P/S ÷ P/FCF) × 100.

        Returns a formatted percentage string (e.g., "26.82%") or "N/A"
        if either source value is missing, non-numeric, or P/FCF is zero
        or negative.
        """
        ps_value: str | None = None
        pfcf_value: str | None = None

        for i in range(0, len(cells) - 1, 2):
            label_text: str = cells[i].get_text(strip=True)
            if label_text == "P/S":
                ps_value = cells[i + 1].get_text(strip=True)
            elif label_text == "P/FCF":
                pfcf_value = cells[i + 1].get_text(strip=True)

        if ps_value is None or pfcf_value is None:
            return "N/A"

        try:
            ps_tokens: list[str] = re.findall(r"-?[\d.]+", ps_value)
            pfcf_tokens: list[str] = re.findall(r"-?[\d.]+", pfcf_value)

            if not ps_tokens or not pfcf_tokens:
                return "N/A"

            ps_num: float = float(ps_tokens[0])
            pfcf_num: float = float(pfcf_tokens[0])

            if pfcf_num <= 0:
                return "N/A"

            fcf_margin: float = (ps_num / pfcf_num) * 100.0
            return f"{fcf_margin:.2f}%"
        except (ValueError, ZeroDivisionError):
            return "N/A"

    def parse_ratios(self, ratio_set: list[RatioInfo]) -> dict[str, str]:
        """
        Extract values for each ratio in ratio_set from the HTML.

        Returns a dict mapping ratio name -> value string.
        Missing ratios get value "N/A".
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
                    results[label_to_name[label_text]] = value_text

            # Handle calculated ratios (empty finviz_label)
            for ratio in ratio_set:
                if ratio.finviz_label == "" and ratio.name == "FCF Margin":
                    results["FCF Margin"] = self._compute_fcf_margin(cells)

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
