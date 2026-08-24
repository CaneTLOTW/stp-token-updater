"""Direct, injectable HTTP client for the token provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

from .models import AuthMethod, SponsorStatus


class ProviderError(Exception):
    """Base provider error."""


class ProviderConnectionError(ProviderError):
    """The provider could not be reached."""


class ProviderAuthenticationError(ProviderError):
    """The selected credential was rejected."""


class ProviderApiError(ProviderError):
    """The provider returned an API error."""


class ProviderRateLimitError(ProviderApiError):
    """The provider asked the caller to slow down."""

    def __init__(self, message: str, *, retry_after: datetime | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class SponsorStatusError(ProviderError):
    """The state response cannot be interpreted."""


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp and normalize it to UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> datetime | None:
    """Parse Retry-After seconds or an HTTP date into an absolute UTC time."""
    if not value:
        return None
    now = now or datetime.now(UTC)
    raw = value.strip()
    try:
        seconds = int(raw)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(now, parsed.astimezone(UTC))
    if seconds < 0:
        return None
    return now + timedelta(seconds=seconds)


def _unwrap_result(payload: Any) -> Any:
    if isinstance(payload, dict) and set(payload) == {"result"}:
        return payload["result"]
    return payload


def parse_sponsor_status(payload: Any) -> SponsorStatus | None:
    """Extract the sponsor subset defensively from a provider state response."""
    state = _unwrap_result(payload)
    if not isinstance(state, dict):
        raise SponsorStatusError("Provider state is not an object")
    sponsor = state.get("sponsor")
    if sponsor is None:
        return None
    if not isinstance(sponsor, dict):
        raise SponsorStatusError("Provider sponsor state is not an object")
    status = sponsor.get("status")
    yaml_source = sponsor.get("yamlSource")
    yaml_source = yaml_source if isinstance(yaml_source, str) else None
    if status is None:
        return SponsorStatus(None, None, False, None, yaml_source)
    if not isinstance(status, dict):
        raise SponsorStatusError("Provider sponsor.status is not an object")
    name = status.get("name") if isinstance(status.get("name"), str) else None
    redacted = status.get("token") if isinstance(status.get("token"), str) else None
    return SponsorStatus(
        name=name,
        expires_at=parse_datetime(status.get("expiresAt")),
        expires_soon=bool(status.get("expiresSoon", False)),
        redacted_token=redacted,
        yaml_source=yaml_source,
    )


class ProviderClient:
    """Provider client with one controlled password re-login on HTTP 401."""

    def __init__(
        self,
        *,
        base_url: str,
        session: aiohttp.ClientSession,
        auth_method: AuthMethod,
        api_key: str | None = None,
        password: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session
        self._auth_method = auth_method
        self._api_key = api_key
        self._password = password
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._auth_cookie: str | None = None
        if auth_method is AuthMethod.API_KEY and not api_key:
            raise ValueError("api_key is required")
        if auth_method is AuthMethod.PASSWORD and not password:
            raise ValueError("password is required")

    @property
    def auth_method(self) -> AuthMethod:
        return self._auth_method

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/{path.lstrip('/')}"

    async def _login(self) -> None:
        if self._auth_method is not AuthMethod.PASSWORD:
            return
        try:
            async with self._session.post(
                self._url("auth/login"),
                json={"password": self._password},
                timeout=self._timeout,
            ) as response:
                if response.status == 401:
                    raise ProviderAuthenticationError("Administrator password rejected")
                if response.status == 429:
                    raise ProviderRateLimitError(
                        "Provider login rate limited",
                        retry_after=parse_retry_after(response.headers.get("Retry-After")),
                    )
                if response.status >= 400:
                    raise ProviderApiError(f"Provider login returned HTTP {response.status}")
                cookie = response.cookies.get("auth")
                if cookie is None or not cookie.value:
                    raise ProviderAuthenticationError("Provider login returned no auth cookie")
                self._auth_cookie = cookie.value
        except ProviderError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ProviderConnectionError("Provider login request failed") from exc

    def _headers(self, protected: bool, headers: dict[str, str] | None) -> dict[str, str]:
        result = dict(headers or {})
        if not protected:
            return result
        if self._auth_method is AuthMethod.API_KEY:
            result["Authorization"] = f"Bearer {self._api_key}"
        elif self._auth_cookie:
            result["Cookie"] = f"auth={self._auth_cookie}"
        return result

    async def _request(
        self,
        method: str,
        path: str,
        *,
        protected: bool = False,
        retry_auth: bool = True,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        if protected and self._auth_method is AuthMethod.PASSWORD and not self._auth_cookie:
            await self._login()
        try:
            async with self._session.request(
                method,
                self._url(path),
                headers=self._headers(protected, headers),
                timeout=self._timeout,
                **kwargs,
            ) as response:
                if response.status == 401:
                    if protected and self._auth_method is AuthMethod.PASSWORD and retry_auth:
                        self._auth_cookie = None
                        await self._login()
                        return await self._request(
                            method,
                            path,
                            protected=protected,
                            retry_auth=False,
                            headers=headers,
                            **kwargs,
                        )
                    raise ProviderAuthenticationError("Provider authentication rejected")
                if response.status == 429:
                    raise ProviderRateLimitError(
                        f"Provider {method.upper()} /api/{path.lstrip('/')} rate limited",
                        retry_after=parse_retry_after(response.headers.get("Retry-After")),
                    )
                if response.status >= 400:
                    raise ProviderApiError(
                        f"Provider {method.upper()} /api/{path.lstrip('/')} returned HTTP {response.status}"
                    )
                if response.status == 204:
                    return None
                try:
                    return await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    body = await response.text()
                    return body.strip() or None
        except ProviderError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ProviderConnectionError(
                f"Provider {method.upper()} /api/{path.lstrip('/')} request failed"
            ) from exc

    async def async_get_state(self) -> dict[str, Any]:
        payload = await self._request("GET", "state")
        if not isinstance(payload, dict):
            raise ProviderApiError("Provider /api/state did not return an object")
        return payload

    async def async_get_sponsor_status(self) -> SponsorStatus | None:
        return parse_sponsor_status(await self.async_get_state())

    async def async_validate_credentials(self) -> None:
        """Validate credentials without changing provider configuration."""
        if self._auth_method is AuthMethod.PASSWORD:
            await self._login()
        result = await self._request("GET", "auth/status", protected=True)
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        valid = result is True or (isinstance(result, str) and result.lower() == "true")
        if isinstance(result, dict):
            valid = bool(result.get("authenticated", result.get("authorized", False)))
        if not valid:
            raise ProviderAuthenticationError("Provider authentication status is false")

    async def async_set_sponsor_token(self, token: str) -> Any:
        """Submit one candidate; callers must verify by read-after-write."""
        return await self._request(
            "POST",
            "config/sponsortoken",
            protected=True,
            json={"token": token},
        )
