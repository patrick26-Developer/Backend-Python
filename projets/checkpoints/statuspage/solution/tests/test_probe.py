"""Sonde HTTP : verdict up/down, latence, gestion des erreurs réseau."""

from __future__ import annotations

import httpx
from statuspage.probe import probe


async def test_probe_up_when_status_matches() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200)))
    result = await probe(client, "https://svc.example", expected_status=200)
    assert result.up is True
    assert result.status_code == 200
    assert result.error is None
    assert result.latency_ms >= 0


async def test_probe_down_when_status_differs() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(503)))
    result = await probe(client, "https://svc.example", expected_status=200)
    assert result.up is False
    assert result.status_code == 503
    assert "503" in (result.error or "")


async def test_probe_down_on_network_error() -> None:
    def _boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    client = httpx.AsyncClient(transport=httpx.MockTransport(_boom))
    result = await probe(client, "https://svc.example", expected_status=200)
    assert result.up is False
    assert result.status_code is None
    assert result.error == "ConnectError"
