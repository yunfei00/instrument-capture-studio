from instrument_capture_studio.workflows.context import (
    CaptureContext,
)
from instrument_capture_studio.workflows.result_sink import (
    InMemoryResultSink,
)


def test_in_memory_sink_stores_snapshot():
    sink = InMemoryResultSink()

    context = CaptureContext()

    context.metadata[
        "value"
    ] = 123

    output_files = sink.save(
        "job-001",
        context,
    )

    assert output_files == ()

    saved = sink.get(
        "job-001"
    )

    assert saved is not context

    assert (
        saved.metadata["value"]
        == 123
    )

    context.metadata[
        "value"
    ] = 456

    assert (
        saved.metadata["value"]
        == 123
    )
