"""Traçage distribué (OpenTelemetry).

Désactivé par défaut. Activé par `APP_OTEL_ENABLED=true` :
- sans `APP_OTEL_ENDPOINT` : exporteur **console** (dev — les spans s'affichent) ;
- avec : exporteur **OTLP/HTTP** vers un *collector* (Jaeger, Tempo, Datadog…).

L'auto-instrumentation crée les spans (HTTP, SQL) sans toucher au code métier.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger("taskman.tracing")
_configured = False


def configure_tracing(*, enabled: bool, endpoint: str | None, service_name: str) -> None:
    global _configured
    if not enabled or _configured:
        return

    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))

    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter: object = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))  # type: ignore[arg-type]
    trace.set_tracer_provider(provider)
    _configured = True
    _logger.info("tracing configuré (endpoint=%s)", endpoint or "console")


def instrument_app(app: object) -> None:
    """Auto-instrumente FastAPI (un span par requête)."""
    if not _configured:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]


def instrument_engine(sync_engine: object) -> None:
    """Auto-instrumente SQLAlchemy (un span par requête SQL)."""
    if not _configured:
        return
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=sync_engine)
