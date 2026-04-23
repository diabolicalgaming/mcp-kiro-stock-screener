"""Web scraper for fetching stock data from finviz.com."""

from __future__ import annotations

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from webdriver_manager.chrome import ChromeDriverManager


class ScrapeError(Exception):
    """Raised when the finviz page cannot be retrieved."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message: str = message
        self.status_code: int | None = status_code
        super().__init__(self.message)


class FinvizScraper:  # pylint: disable=too-few-public-methods
    """Scrapes stock data from finviz.com using Selenium."""

    BASE_URL: str = "https://finviz.com/quote.ashx?t={ticker}"

    def __init__(self) -> None:
        self._options: Options = self._build_options()
        self._service: Service = self._build_service()

    def _build_options(self) -> Options:
        """Configure headless Chrome options with appropriate user-agent."""
        options: Options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        return options

    def _build_service(self) -> Service:
        """Build a Chrome Service using webdriver-manager to auto-resolve chromedriver."""
        try:
            driver_path: str = ChromeDriverManager().install()
            return Service(executable_path=driver_path)
        except Exception as exc:
            raise ScrapeError(
                message=f"Failed to install/locate chromedriver: {exc}",
                status_code=None,
            ) from exc

    def fetch_page(self, ticker: str) -> str:
        """
        Fetch the finviz quote page HTML for the given ticker.

        Returns the page source HTML string.
        Raises ScrapeError on failure.
        """
        driver: webdriver.Chrome | None = None
        try:
            driver = webdriver.Chrome(
                service=self._service,
                options=self._options,
            )
            url: str = self.BASE_URL.format(ticker=ticker)
            driver.get(url)
            page_source: str = driver.page_source
            return page_source
        except WebDriverException as exc:
            raise ScrapeError(
                message=f"Failed to fetch page for ticker '{ticker}': {exc.msg}",
                status_code=None,
            ) from exc
        except Exception as exc:
            raise ScrapeError(
                message=f"Unexpected error fetching page for ticker '{ticker}': {exc}",
                status_code=None,
            ) from exc
        finally:
            if driver is not None:
                driver.quit()
