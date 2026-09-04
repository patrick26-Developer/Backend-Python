"""Sonde HTTP d'un service : une requête, un verdict."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ProbeResult:
    up: bool
    status_code: int | None
    latency_ms: float
    error: str | None


async def probe(client: httpx.AsyncClient, url: str, *, expected_status: int) -> ProbeResult:
    start = time.perf_counter()
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        return ProbeResult(
            up=False,
            status_code=None,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            error=type(exc).__name__,
        )
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    up = response.status_code == expected_status
    return ProbeResult(
        up=up,
        status_code=response.status_code,
        latency_ms=latency_ms,
        error=None if up else f"status {response.status_code} != {expected_status}",
    )
