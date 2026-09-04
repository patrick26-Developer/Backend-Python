"""Logs structurés corrélés + métriques Prometheus.

Chaque ligne de log porte un identifiant de corrélation : `request_id` (API) **ou**
`check_id` (worker de sonde), via une `ContextVar`.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, level: str, json_output: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _JsonFormatter()
        if json_output
        else logging.Formatter("%(levelname)-5s [%(name)s] [%(message)s]")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


# --- métriques : un registre dédié (isolé entre deux `create_app` en test) ----
class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.checks_total = Counter(
            "statuspage_checks_total", "Sondes effectuées", ["service"], registry=self.registry
        )
        self.check_failures_total = Counter(
            "statuspage_check_failures_total",
            "Sondes en échec",
            ["service"],
            registry=self.registry,
        )
        self.check_latency = Histogram(
            "statuspage_check_latency_seconds",
            "Latence des sondes",
            ["service"],
            registry=self.registry,
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

    def record(self, service: str, *, up: bool, latency_ms: float) -> None:
        self.checks_total.labels(service).inc()
        if not up:
            self.check_failures_total.labels(service).inc()
        self.check_latency.labels(service).observe(latency_ms / 1000)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
