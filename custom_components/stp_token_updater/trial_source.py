"""Official public trial-token source."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

import aiohttp

from .api import parse_retry_after
from .const import ALLOWED_SOURCE_HOSTS, DEFAULT_SOURCE_URL
from .models import TrialTokenCandidate
from .token import TrialTokenParseError, select_latest_trial_candidate


class TrialSourceError(Exception):
    """The official source could not be fetched or parsed."""

    def __init__(self, message: str, *, retry_after: datetime | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TrialTokenSource:
    """Fetch and parse the latest plausible trial candidate."""

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        source_url: str = DEFAULT_SOURCE_URL,
        timeout_seconds: float = 15.0,
    ) -> None:
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS:
            raise ValueError("trial source must use an allowed HTTPS host")
        self._session = session
        self.source_url = source_url
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def async_get_latest(self, *, now: datetime | None = None) -> TrialTokenCandidate:
        now = now or datetime.now(UTC)
        try:
            async with self._session.get(
                self.source_url,
                timeout=self._timeout,
                allow_redirects=True,
                headers={"Accept": "text/html,application/xhtml+xml"},
            ) as response:
                final = response.url
                if final.scheme != "https" or final.host not in ALLOWED_SOURCE_HOSTS:
                    raise TrialSourceError("trial source redirected to an unexpected host")
                if response.status == 429:
                    raise TrialSourceError(
                        "trial source rate limited HTTP 429",
                        retry_after=parse_retry_after(response.headers.get("Retry-After"), now=now),
                    )
                if response.status != 200:
                    raise TrialSourceError(f"trial source returned HTTP {response.status}")
                content = await response.text()
        except TrialSourceError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise TrialSourceError("failed to retrieve trial source") from exc
        try:
            return select_latest_trial_candidate(content, now=now)
        except TrialTokenParseError as exc:
            raise TrialSourceError("official page contains no valid trial token") from exc
