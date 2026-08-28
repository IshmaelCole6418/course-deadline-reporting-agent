from datetime import datetime, timezone
from types import SimpleNamespace

from course_reporting.reporting_loop import CourseDelivery, run_reporting_loop


class FakeMessage:
    def __init__(self, calls):
        self.tool_calls = calls

    def model_dump(self, *, exclude_none=True):
        return {"role": "assistant", "tool_calls": []}


def tool_call(call_id, name, arguments="{}"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class FakeCompletions:
    def __init__(self):
        self.responses = iter(
            [
                FakeMessage(
                    [
                        tool_call("one", "check_deadline", '{"learner_id":"late"}'),
                        tool_call("two", "check_deadline", '{"learner_id":"done"}'),
                    ]
                ),
                FakeMessage([tool_call("three", "build_educator_report")]),
            ]
        )

    def create(self, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=next(self.responses))])


def test_overdue_learner_reaches_the_educator_report():
    delivery = CourseDelivery.model_validate(
        {
            "course_id": "storefront-course",
            "lesson_id": "checkout",
            "delivered_at": "2026-08-15T09:00:00Z",
            "learners": [
                {"learner_id": "late", "due_at": "2026-08-16T09:00:00Z"},
                {
                    "learner_id": "done",
                    "due_at": "2026-08-18T09:00:00Z",
                    "submitted_at": "2026-08-16T08:00:00Z",
                },
            ],
        }
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    report = run_reporting_loop(
        delivery,
        client=client,
        now=datetime(2026, 8, 17, 9, tzinfo=timezone.utc),
    )

    assert report.overdue_learner_ids == ["late"]
    assert report.submitted_learner_ids == ["done"]
    assert report.pending_learner_ids == []
