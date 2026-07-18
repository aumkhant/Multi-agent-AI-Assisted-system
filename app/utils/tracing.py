import logging
from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("tracing")

_tracer_provider: TracerProvider | None = None


def _initialize_tracing() -> None:
    global _tracer_provider
    if _tracer_provider is not None:
        return

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer_provider = provider


_initialize_tracing()


@contextmanager
def trace_operation(operation_name: str, metadata: dict[str, Any] | None = None) -> Iterator[Any]:
    """Wrap an operation in an OpenTelemetry span with structured metadata."""
    tracer = trace.get_tracer("app.utils.tracing")
    with tracer.start_as_current_span(operation_name) as span:
        for key, value in (metadata or {}).items():
            if isinstance(value, (str, bool, int, float)):
                span.set_attribute(key, value)
            else:
                span.set_attribute(key, str(value))

        logger.info("trace.start", extra={"event": "trace.start", "operation": operation_name, **(metadata or {})})
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.exception(
                "trace.error",
                extra={"event": "trace.error", "operation": operation_name, "error": str(exc), **(metadata or {})},
            )
            raise
        else:
            span.set_status(Status(StatusCode.OK))
            logger.info(
                "trace.success",
                extra={"event": "trace.success", "operation": operation_name, **(metadata or {})},
            )
