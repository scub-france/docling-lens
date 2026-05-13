from domain.value_objects import ReasoningIteration, ReasoningResult, ReasoningStepKind
from infra.trace_builder import build_trace


def test_build_trace_maps_iterations_to_read_steps() -> None:
    result = ReasoningResult(
        answer="2.45 pages/sec",
        converged=True,
        iterations=[
            ReasoningIteration(
                iteration=1,
                section_ref="#/texts/12",
                reason="Looks like the throughput table",
                section_text_length=187,
                can_answer=True,
                response="M3 Max default = 2.45 p/s",
            ),
        ],
    )

    trace = build_trace(result=result, model_id="mistral-small3.2")

    assert trace.answer == "2.45 pages/sec"
    assert trace.converged is True
    assert trace.model_id == "mistral-small3.2"
    assert len(trace.steps) == 1
    step = trace.steps[0]
    assert step.kind is ReasoningStepKind.READ
    # Title is now the agent's stated reason — much more useful than "Read #/.../N".
    assert step.title == "Looks like the throughput table"
    # When can_answer, the summary surfaces the response.
    assert step.summary == "M3 Max default = 2.45 p/s"
    assert step.citations == ["#/texts/12"]
    assert step.payload["section_ref"] == "#/texts/12"
    assert step.payload["can_answer"] is True


def test_build_trace_marks_insufficient_section_when_cannot_answer() -> None:
    result = ReasoningResult(
        answer="",
        converged=False,
        iterations=[
            ReasoningIteration(
                iteration=1,
                section_ref="#/texts/3",
                reason="Out-of-scope intro section",
                section_text_length=42,
                can_answer=False,
                response="",
            ),
        ],
    )

    trace = build_trace(result=result, model_id="x")

    step = trace.steps[0]
    assert step.title == "Out-of-scope intro section"
    assert "Insufficient" in step.summary
    assert "42 chars" in step.summary
    assert step.payload["can_answer"] is False


def test_build_trace_truncates_long_titles() -> None:
    long_reason = "x" * 200
    result = ReasoningResult(
        answer="",
        converged=False,
        iterations=[
            ReasoningIteration(
                iteration=1,
                section_ref="#/texts/1",
                reason=long_reason,
                section_text_length=10,
                can_answer=False,
                response="",
            ),
        ],
    )

    trace = build_trace(result=result, model_id="x")

    assert len(trace.steps[0].title) <= 96
    assert trace.steps[0].title.endswith("…")
