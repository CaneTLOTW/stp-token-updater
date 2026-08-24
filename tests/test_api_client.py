from __future__ import annotations

import asyncio
from types import SimpleNamespace

from custom_components.stp_token_updater.api import ProviderClient
from custom_components.stp_token_updater.models import AuthMethod


class _Response:
    def __init__(
        self,
        status: int,
        *,
        payload=None,
        cookie: str | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self.headers: dict[str, str] = {}
        self.cookies = (
            {"auth": SimpleNamespace(value=cookie)} if cookie is not None else {}
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def json(self, *, content_type=None):
        return self._payload

    async def text(self) -> str:
        return ""


class _Session:
    def __init__(self, *, logins: list[_Response], requests: list[_Response]) -> None:
        self._logins = logins
        self._requests = requests
        self.calls: list[tuple[str, str, dict]] = []

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._logins.pop(0)

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._requests.pop(0)


def test_password_session_reauthenticates_once_after_401() -> None:
    """A stale password cookie gets exactly one fresh login and one retry."""
    session = _Session(
        logins=[_Response(200, cookie="first"), _Response(200, cookie="second")],
        requests=[_Response(401), _Response(200, payload=True)],
    )
    client = ProviderClient(
        base_url="http://provider.example:7070",
        session=session,
        auth_method=AuthMethod.PASSWORD,
        password="test-password",
    )

    asyncio.run(client.async_validate_credentials())

    assert [call[0] for call in session.calls] == ["POST", "GET", "POST", "GET"]
    protected_calls = [call for call in session.calls if call[0] == "GET"]
    assert protected_calls[0][2]["headers"]["Cookie"] == "auth=first"
    assert protected_calls[1][2]["headers"]["Cookie"] == "auth=second"


def test_api_key_uses_bearer_header_for_protected_request() -> None:
    session = _Session(logins=[], requests=[_Response(200, payload=True)])
    client = ProviderClient(
        base_url="http://provider.example:7070",
        session=session,
        auth_method=AuthMethod.API_KEY,
        api_key="test-key",
    )

    asyncio.run(client.async_validate_credentials())

    assert len(session.calls) == 1
    assert session.calls[0][2]["headers"]["Authorization"] == "Bearer test-key"
