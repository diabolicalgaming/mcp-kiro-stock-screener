"""Industry average provider using the OpenAI API."""

from __future__ import annotations

import json
import hashlib
import datetime
from typing import TYPE_CHECKING
from collections.abc import Mapping

import openai
from openai import OpenAI

from rich.console import Console

from stock_screener.ratios import RatioInfo

if TYPE_CHECKING:
    from stock_screener.cache import IndustryAverageCache


class IndustryAverageProvider:
    """Fetches industry-average ratio values via the OpenAI API."""

    MODEL: str = "gpt-5.4-mini"
    TEMPERATURE: float = 0.0

    def __init__(self, api_key: str) -> None:
        self._client: OpenAI = OpenAI(api_key=api_key)
        self._console: Console = Console()

    @staticmethod
    def _generate_seed(ticker: str, stock_type: str) -> int:
        """Generate a deterministic seed from the ticker and stock type."""
        key: str = f"{ticker.upper()}:{stock_type.lower()}"
        hash_digest: str = hashlib.sha256(key.encode()).hexdigest()
        return int(hash_digest[:8], 16)

    def _build_prompt(
        self,
        ratio_set: list[RatioInfo],
        sector: str,
        industry: str,
    ) -> str:
        """
        Build a concise, token-efficient prompt requesting industry-average
        values for only the ratio names in the active ratio set.

        Uses sector and industry from finviz for specific context, and
        format-aware instructions so the model returns percentage strings
        for percentage ratios and plain number strings for multiple ratios.
        """
        current_year: int = datetime.date.today().year

        percentage_ratios: list[RatioInfo] = [
            r for r in ratio_set if r.format_type == "percentage"
        ]
        multiple_ratios: list[RatioInfo] = [
            r for r in ratio_set if r.format_type == "multiple"
        ]

        blocks: list[str] = [
            f"What are the approximate industry-average financial ratios "
            f"for the {industry} sector ({sector}) for the current year "
            f"{current_year}? For growth metrics like EPS YoY, use the "
            f"sector median annual growth rate."
        ]

        if percentage_ratios:
            percentage_template: dict[str, str] = {
                r.name: "" for r in percentage_ratios
            }
            blocks.append(
                f"Fill in this JSON template (keep keys unchanged, "
                f"values must be non-empty percentage strings "
                f"(e.g. '15%')): {json.dumps(percentage_template)}"
            )

        if multiple_ratios:
            multiple_template: dict[str, str] = {
                r.name: "" for r in multiple_ratios
            }
            blocks.append(
                f"Fill in this JSON template (keep keys unchanged, "
                f"values must be non-empty plain number strings "
                f"without '%' (e.g. '22.0')): "
                f"{json.dumps(multiple_template)}"
            )

        blocks.append(
            "Return a single JSON object combining all keys above."
        )

        return " ".join(blocks)

    def _default_averages(
        self,
        ratio_set: list[RatioInfo],
    ) -> dict[str, str]:
        """Return a dict with 'N/A' for every ratio in the set."""
        return {r.name: "N/A" for r in ratio_set}

    @staticmethod
    def _normalize_key(key: str) -> str:
        """Lowercase, strip whitespace, and collapse non-alphanumeric chars."""
        return "".join(ch for ch in key.lower() if ch.isalnum())

    def _match_response(
        self,
        data: Mapping[str, object],
        ratio_set: list[RatioInfo],
    ) -> dict[str, str]:
        """
        Map OpenAI response keys to ratio names using exact match first,
        then normalized fuzzy match.  Converts None / empty values to 'N/A'.
        """
        normalized_data: dict[str, str] = {
            self._normalize_key(k): str(v) if v is not None else "N/A"
            for k, v in data.items()
        }
        result: dict[str, str] = {}
        for ratio in ratio_set:
            value: str | None = None
            if ratio.name in data and data[ratio.name] is not None:
                value = str(data[ratio.name])
            else:
                norm_name: str = self._normalize_key(ratio.name)
                value = normalized_data.get(norm_name)
            if value is None or value.strip() in ("", "None", "null"):
                value = "N/A"
            result[ratio.name] = value
        return result

    def fetch_averages(
        self,
        ticker: str,
        stock_type: str,
        ratio_set: list[RatioInfo],
        sector: str,
        industry: str,
    ) -> dict[str, str]:
        """
        Send the prompt to OpenAI and parse the response into a dict
        mapping ratio name -> industry average value string.
        """
        try:
            prompt: str = self._build_prompt(
                ratio_set, sector, industry
            )
            seed: int = self._generate_seed(ticker, stock_type)
            response = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return JSON only. No explanation. "
                            "Every value must be a non-empty string."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.TEMPERATURE,
                seed=seed,
                response_format={"type": "json_object"},
            )
            content: str | None = response.choices[0].message.content
            if content is None:
                self._console.print(
                    "[yellow]Warning: Empty response from OpenAI API.[/yellow]"
                )
                return self._default_averages(ratio_set)

            data: dict[str, str] = json.loads(content)
            result: dict[str, str] = self._match_response(
                data, ratio_set
            )
            return result

        except openai.RateLimitError:
            self._console.print(
                "[red]Error: OpenAI API rate limit reached — "
                "account may not have sufficient funds.[/red]"
            )
            return self._default_averages(ratio_set)

        except (openai.APIStatusError, openai.APIConnectionError) as exc:
            self._console.print(
                f"[red]Error: OpenAI API error — {exc}[/red]"
            )
            return self._default_averages(ratio_set)

        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            self._console.print(
                f"[yellow]Warning: Could not parse OpenAI response — {exc}[/yellow]"
            )
            return self._default_averages(ratio_set)

        except (OSError, ValueError, RuntimeError) as exc:
            self._console.print(
                f"[red]Error: Unexpected error fetching industry averages — {exc}[/red]"
            )
            return self._default_averages(ratio_set)


def resolve_industry_averages(
    provider: IndustryAverageProvider,
    cache: IndustryAverageCache,
    ticker: str,
    stock_type: str,
    ratio_set: list[RatioInfo],
    sector: str,
    industry: str,
    use_cache: bool,
    refresh: bool,
) -> dict[str, str]:
    """Resolve industry averages using cache-then-fetch strategy.

    Checks the cache first (unless disabled or refreshing), falls back
    to the OpenAI API on miss, and writes successful results to cache.
    Returns N/A fallback values on any provider failure.

    This function is shared by both the CLI app and the MCP server
    to avoid duplicating the cache-check-then-fetch logic.
    """
    industry_averages: dict[str, str] | None = None

    if use_cache and not refresh:
        industry_averages = cache.get(ticker, stock_type)

    if industry_averages is None:
        try:
            industry_averages = provider.fetch_averages(
                ticker, stock_type, ratio_set, sector, industry
            )
            if use_cache:
                cache.put(ticker, stock_type, industry_averages)
        except (
            OSError, ValueError, TypeError, KeyError, RuntimeError,
        ):
            industry_averages = {r.name: "N/A" for r in ratio_set}

    return industry_averages
