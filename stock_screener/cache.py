"""File-based cache for industry average data."""

from __future__ import annotations

import json
import datetime
from pathlib import Path

from filelock import FileLock
from filelock import Timeout

from rich.console import Console


class IndustryAverageCache:
    """
    Persists industry-average values to a local JSON file.

    Uses cross-platform file locking (filelock.FileLock) to ensure atomic
    read-modify-write operations when multiple processes access
    the cache concurrently. Works on macOS, Linux, and Windows.

    Cache structure:
    {
        "AAPL": {
            "div":    {"timestamp": "...", "averages": {...}},
            "growth": {"timestamp": "...", "averages": {...}},
            "value":  {"timestamp": "...", "averages": {...}}
        }
    }
    """

    DEFAULT_TTL_DAYS: int = 7
    _CACHE_DIR: str = ".stock_screener"
    _CACHE_FILE: str = "cache.json"
    _LOCK_FILE: str = "cache.json.lock"
    _LOCK_TIMEOUT_SECONDS: int = 10

    def __init__(self, ttl_days: int = DEFAULT_TTL_DAYS) -> None:
        self._ttl_days: int = ttl_days
        self._cache_path: Path = self._resolve_cache_path()
        self._lock_path: Path = self._cache_path.parent / self._LOCK_FILE
        self._lock: FileLock = FileLock(
            str(self._lock_path), timeout=self._LOCK_TIMEOUT_SECONDS
        )
        self._console: Console = Console()

    def _resolve_cache_path(self) -> Path:
        """Return the full path to the cache JSON file, creating dirs if needed."""
        cache_dir: Path = Path.home() / self._CACHE_DIR
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._console.print(
                f"[yellow]Warning: Could not create cache directory — {exc}[/yellow]"
            )
        return cache_dir / self._CACHE_FILE

    def _load(self) -> dict[str, dict[str, dict[str, object]]]:
        """Load the entire cache file. Returns empty dict on any failure."""
        try:
            if not self._cache_path.exists():
                return {}
            text: str = self._cache_path.read_text(encoding="utf-8")
            data: dict[str, dict[str, dict[str, object]]] = json.loads(text)
            return data
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            self._console.print(
                f"[yellow]Warning: Could not read cache — {exc}[/yellow]"
            )
            return {}

    def _save(self, data: dict[str, dict[str, dict[str, object]]]) -> None:
        """Write the full cache dict to disk."""
        try:
            self._cache_path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self._console.print(
                f"[yellow]Warning: Could not write cache — {exc}[/yellow]"
            )

    def _is_expired(self, timestamp_str: str) -> bool:
        """Return True if the timestamp is older than the configured TTL."""
        try:
            cached_time: datetime.datetime = datetime.datetime.fromisoformat(
                timestamp_str
            )
            age: datetime.timedelta = datetime.datetime.now() - cached_time
            return age.days >= self._ttl_days
        except (ValueError, TypeError):
            return True

    def _read_entry(
        self,
        data: dict[str, dict[str, dict[str, object]]],
        ticker: str,
        stock_type: str,
    ) -> dict[str, str] | None:
        """Extract a cached entry from loaded data, or None on miss/expiry."""
        ticker_key: str = ticker.upper()
        ticker_entry: dict[str, dict[str, object]] | None = data.get(
            ticker_key
        )
        if ticker_entry is None:
            return None
        type_entry: dict[str, object] | None = ticker_entry.get(stock_type)
        if type_entry is None:
            return None
        timestamp: object = type_entry.get("timestamp")
        if not isinstance(timestamp, str) or self._is_expired(timestamp):
            return None
        averages: object = type_entry.get("averages")
        if not isinstance(averages, dict):
            return None
        return {str(k): str(v) for k, v in averages.items()}

    def get(
        self,
        ticker: str,
        stock_type: str,
    ) -> dict[str, str] | None:
        """
        Return cached averages for ticker/stock_type, or None on miss/expiry.

        Acquires an exclusive file lock before reading to ensure a consistent
        snapshot of the cache file. Falls back to unlocked read on timeout.
        """
        try:
            with self._lock:
                data: dict[str, dict[str, dict[str, object]]] = self._load()
                return self._read_entry(data, ticker, stock_type)
        except Timeout:
            self._console.print(
                "[yellow]Warning: Could not acquire cache lock "
                f"within {self._LOCK_TIMEOUT_SECONDS}s — "
                "proceeding without lock[/yellow]"
            )
            data = self._load()
            return self._read_entry(data, ticker, stock_type)

    def put(
        self,
        ticker: str,
        stock_type: str,
        averages: dict[str, str],
    ) -> None:
        """
        Store averages for ticker/stock_type with the current timestamp.

        Acquires an exclusive file lock, reads the current cache state,
        merges the new entry, and writes back — ensuring the entire
        read-modify-write cycle is atomic. Falls back to unlocked
        write on timeout.
        """
        try:
            with self._lock:
                data: dict[str, dict[str, dict[str, object]]] = self._load()
                ticker_key: str = ticker.upper()
                if ticker_key not in data:
                    data[ticker_key] = {}
                data[ticker_key][stock_type] = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "averages": averages,
                }
                self._save(data)
        except Timeout:
            self._console.print(
                "[yellow]Warning: Could not acquire cache lock "
                f"within {self._LOCK_TIMEOUT_SECONDS}s — "
                "proceeding without lock[/yellow]"
            )
            data = self._load()
            ticker_key = ticker.upper()
            if ticker_key not in data:
                data[ticker_key] = {}
            data[ticker_key][stock_type] = {
                "timestamp": datetime.datetime.now().isoformat(),
                "averages": averages,
            }
            self._save(data)
