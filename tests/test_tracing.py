import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from app.utils.llm import _extract_usage_metadata
from app.utils.tracing import trace_operation


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_extract_usage_metadata_uses_provider_token_counts():
    class FakeUsage:
        input_tokens = 12
        output_tokens = 5
        total_tokens = 17

    class FakeResult:
        usage = FakeUsage()

    metadata = _extract_usage_metadata(FakeResult())
    assert metadata["gen_ai.usage.input_tokens"] == 12
    assert metadata["gen_ai.usage.output_tokens"] == 5
    assert metadata["gen_ai.usage.total_tokens"] == 17


def test_trace_operation_preserves_exceptions_and_records_span():
    exporter = RecordingSpanExporter()
    provider = trace.get_tracer_provider()
    if hasattr(provider, "add_span_processor"):
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    with pytest.raises(ValueError, match="boom"):
        with trace_operation("demo.operation", {"component": "tests"}):
            raise ValueError("boom")

    assert any(span.name == "demo.operation" for span in exporter.spans)
