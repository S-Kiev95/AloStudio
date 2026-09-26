"""HTTP requests to URLs that somebody typed.

Webhook endpoints, bot endpoints, push subscriptions and attachment URLs
all arrive from users — and several of them from users who are barely
authenticated: a widget visitor, a webhook payload that nobody verified.
The server then fetches them from *inside* its own network. Left alone,
that is a way to make AloStudio request ``http://127.0.0.1:…``, the cloud
metadata service, MinIO, the Tailscale local API at ``100.100.100.100``, or
whatever else shares the machine — and, where the response is handed back
(the attachment proxy, an email attachment), to read it.

:func:`guarded_client` is an ``httpx.AsyncClient`` whose request hook
refuses any destination that is not a public address. It runs for every
request the client sends, redirects included, so a public URL that
answers ``302 Location: http://127.0.0.1`` is refused at the second hop
rather than followed.

Two deliberate allowances:

* **Our own object store.** It is usually MinIO on localhost, and it is
  where uploads live; the attachment proxy exists to reach it. Only its
  exact origin is allowed.
* ``allow_private_outbound_urls`` — for local development that points a
  webhook at a service on the same machine. Never set it on a server
  reachable from outside.

What this does not stop: DNS rebinding between our lookup and httpx's
own. Closing that needs connecting to the address we checked, which
httpx does not expose cleanly. The window is one resolution wide.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings


class BlockedDestination(httpx.RequestError):
    """The URL points somewhere the server must not reach.

    A ``RequestError`` on purpose: every caller already handles a failed
    request, and a refused destination should take exactly that path —
    logged, retried or dead-lettered — rather than a new one.
    """


def _origin(url: str) -> tuple[str, str, int | None] | None:
    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        return None
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.scheme.lower(), parts.hostname.lower(), port


def _is_our_store(url: str) -> bool:
    endpoint = get_settings().s3_endpoint_url
    if not endpoint:
        return False
    return _origin(url) == _origin(endpoint)


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # ``is_global`` is False for loopback, RFC 1918, link-local (the cloud
    # metadata address), and 100.64.0.0/10 — the range Tailscale uses.
    return ip.is_global


async def check_destination(url: str) -> None:
    """Raise :class:`BlockedDestination` unless ``url`` is safe to fetch."""
    request = httpx.Request("GET", url)
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BlockedDestination("only http(s) URLs are allowed", request=request)

    if _is_our_store(url) or get_settings().allow_private_outbound_urls:
        return

    host = parts.hostname
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(
                host, parts.port or 443, type=socket.SOCK_STREAM
            )
        except socket.gaierror:
            # Unresolvable here is unresolvable for httpx too, so the
            # request fails on its own; refusing it would only add a
            # second, less accurate error.
            return
        addresses = [str(info[4][0]) for info in infos]

    for address in addresses:
        if not _is_public(address):
            raise BlockedDestination(
                f"destination {host} resolves to a non-public address",
                request=request,
            )


async def _refuse_private(request: httpx.Request) -> None:
    await check_destination(str(request.url))


def guarded_client(**kwargs: Any) -> httpx.AsyncClient:
    """``httpx.AsyncClient`` that refuses non-public destinations."""
    hooks: dict[str, list[Any]] = dict(kwargs.pop("event_hooks", None) or {})
    hooks["request"] = [*hooks.get("request", []), _refuse_private]
    return httpx.AsyncClient(event_hooks=hooks, **kwargs)


__all__ = ["BlockedDestination", "check_destination", "guarded_client"]
