"""The guard on requests to URLs that users typed.

Written against IP literals so no test depends on DNS: what is being
checked is the decision about an *address*, and a hostname only adds a
resolver that may or may not be there.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.core.outbound import BlockedDestination, check_destination, guarded_client


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_OUTBOUND_URLS", raising=False)
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://127.0.0.1:9100")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/health",  # the backend itself
        "http://localhost:6380/",  # loopback by name
        "http://10.0.0.5/",  # RFC 1918
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://100.100.100.100/localapi/v0/status",  # Tailscale local API
        "http://[::1]:8000/",
        "http://[::ffff:127.0.0.1]/",  # IPv4 hidden in IPv6
        "http://0.0.0.0:8000/",
    ],
)
async def test_internal_destinations_are_refused(url):
    with pytest.raises(BlockedDestination):
        await check_destination(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://x/", "ftp://1.1.1.1/"])
async def test_only_http_is_allowed(url):
    with pytest.raises(BlockedDestination):
        await check_destination(url)


async def test_a_public_address_is_allowed():
    await check_destination("https://93.184.216.34/hook")


async def test_our_own_object_store_is_allowed_even_on_localhost():
    # The attachment proxy exists to reach it; only its exact origin passes.
    await check_destination("http://127.0.0.1:9100/bucket/a.png")
    with pytest.raises(BlockedDestination):
        await check_destination("http://127.0.0.1:9101/bucket/a.png")


async def test_development_can_opt_in(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_OUTBOUND_URLS", "true")
    get_settings.cache_clear()
    await check_destination("http://127.0.0.1:8000/health")


@respx.mock
async def test_a_redirect_into_the_network_is_refused_at_the_second_hop():
    """A public URL answering ``302 → 127.0.0.1`` must not be followed.

    Checking only the URL we were given would miss this; the guard runs
    as a request hook, so it sees every hop.
    """
    respx.get("http://93.184.216.34/img").mock(
        return_value=httpx.Response(
            302, headers={"Location": "http://127.0.0.1:8000/health"}
        )
    )
    internal = respx.get("http://127.0.0.1:8000/health").mock(
        return_value=httpx.Response(200, text="secreto")
    )

    async with guarded_client(follow_redirects=True) as client:
        with pytest.raises(BlockedDestination):
            await client.get("http://93.184.216.34/img")
    assert not internal.called


@respx.mock
async def test_a_refusal_is_an_ordinary_request_error():
    """Callers already handle ``httpx.RequestError``; a refused destination
    takes that same path instead of escaping as something new."""
    async with guarded_client() as client:
        with pytest.raises(httpx.RequestError):
            await client.post("http://127.0.0.1:8000/", content=b"{}")
